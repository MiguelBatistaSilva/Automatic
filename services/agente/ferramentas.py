"""
services/agente/ferramentas.py — O que o Assistente sabe fazer.

Cada ferramenta tem quatro partes:
  1. o ESQUEMA que o modelo enxerga (nome, descrição, parâmetros);
  2. `preparar(args)` — valida e normaliza o que o modelo mandou e monta o
     cartão (`Acao`). Devolve `str` quando falta algo: a mensagem volta ao
     modelo, que pergunta ao técnico em vez de chutar;
  3. `executar(args, sessao)` — roda de verdade, chamando os fluxos
     (services/flow_*_pw.py) na página da `Sessao` do plano: um login e uma
     licença para todos os passos (2026-10-01; antes cada ferramenta abria o
     próprio Chrome via bot/services/*). NENHUM arquivo de fluxo foi alterado;
  4. o texto do RESULTADO, montado aqui (determinístico), e não pelo modelo.

LGPD: o resultado da execução (nomes, setores lidos do Assyst) NÃO volta para
a IA — vai direto para a tela. A IA só vê o que o técnico digitou e uma nota
curta de que a ação rodou.

`escreve=True` -> cartão com Confirmar/Cancelar antes de rodar.
`escreve=False` -> só leitura, roda direto (princípio combinado: ler sozinho,
gravar só com confirmação).
"""

import dataclasses
import difflib
import re
import unicodedata
from typing import Callable

from services.requisicao_campos import ORDEM_COLUNAS, POR_CHAVE, SEPARADOR
from services.sla_engine import FILAS, FILA_PADRAO
from services.agente.sessao import ErroSessao, Resultado, Sessao


@dataclasses.dataclass
class Acao:
    ferramenta: str
    args: dict
    titulo: str
    linhas: list[str]
    escreve: bool
    pode_simular: bool = False
    # Situação do checkpoint (fluxos com retomada): "", "novo", "pendente",
    # "concluido" ou "corrompido" — decide quais botões o cartão mostra.
    checkpoint: str = ""
    aviso: str = ""
    # Texto do botão "Copiar lista" do cartão. Na Requisição é o lote EXATO:
    # colado de volta no chat, vira o mesmo lote (ver requisicoes_coladas).
    copiar: str = ""


@dataclasses.dataclass
class Ferramenta:
    nome: str
    # Texto fixo, ou função que monta na hora (ex.: lê tipos/nomes do banco).
    descricao: "str | Callable[[], str]"
    parametros: dict
    preparar: Callable[[dict], "Acao | str"]
    executar: Callable[[dict, "Sessao"], "Resultado"] | None = None
    # Ferramenta LOCAL (sem navegador): roda na hora e o resultado volta ao
    # modelo — só para dados do próprio app, nunca do Assyst.
    local: Callable[[dict], str] | None = None
    # Ferramenta de INVESTIGAÇÃO (2026-10-01): lê o Assyst DURANTE a conversa
    # e o resultado volta ao modelo, para ele decidir o próximo passo (ex.:
    # SLA estourado -> não resolver). Só leitura, e o texto devolvido leva o
    # MÍNIMO (número do chamado, tempo do SLA; nome só de quem o técnico citou).
    investiga: Callable[[dict, "Sessao"], str] | None = None


# --------------------------------------------------------------------------- #
# Ajudantes
# --------------------------------------------------------------------------- #

def _lista(v) -> list[str]:
    """Normaliza uma lista de números (chamados/tombos): aceita lista ou texto
    separado por vírgula/espaço, tira vazios e repetidos, mantém a ordem."""
    if isinstance(v, str):
        v = v.replace(",", " ").replace(";", " ").split()
    vistos, saida = set(), []
    for x in v or []:
        x = str(x).strip()
        if x and x not in vistos:
            vistos.add(x)
            saida.append(x)
    return saida


def _nomes_bases() -> list[str]:
    from services import kb_store
    return [e["nome_artigo"] for e in kb_store.carregar()]


# Palavras que não ajudam a achar a base ("a BASE DE teste DO patch cord").
_PALAVRAS_VAZIAS = {"a", "o", "as", "os", "de", "da", "do", "das", "dos", "e",
                    "em", "na", "no", "para", "com", "bc", "base", "via"}


def _palavras(texto: str) -> list[str]:
    return [p for p in re.findall(r"\w+", _sem_acento(texto or ""))
            if p not in _PALAVRAS_VAZIAS]


def _bases_por_palavras(trecho: str) -> list[str]:
    """Bases cujo nome tem TODAS as palavras do trecho, em qualquer ordem e
    sem acento (06/10): "teste de patch cord" acha "BC - Teste de Cabo Patch
    Cord" — a busca pelo trecho inteiro não achava, por causa do "Cabo"."""
    alvo = _palavras(trecho)
    if not alvo:
        return []
    # Início de palavra: "monitor" acha "Monitores", "instal" acha "Instalação".
    return [n for n in _nomes_bases()
            if all(any(w.startswith(p) for w in _palavras(n)) for p in alvo)]


def _resolver_base(nome: str) -> tuple[str, str]:
    """(nome_exato, erro). Aceita o nome exato (sem diferença de maiúsculas)
    ou, desde 06/10, a ÚNICA base que tem todas as palavras citadas — o nome
    escolhido aparece no cartão antes de confirmar. Mais de uma: pergunta.
    Nunca escolhe por semelhança (base errada não tem desfazer)."""
    nomes = _nomes_bases()
    alvo = (nome or "").strip().lower()
    for n in nomes:
        if n.lower() == alvo:
            return n, ""
    por_palavras = _bases_por_palavras(nome)
    if len(por_palavras) == 1:
        return por_palavras[0], ""
    if len(por_palavras) > 1:
        return "", (f"Mais de uma base tem '{nome}': {', '.join(por_palavras[:10])}. "
                    "Pergunte ao técnico qual delas.")
    parecidas = difflib.get_close_matches(nome or "", nomes, n=8, cutoff=0.3)
    parecidas += [n for n in nomes if alvo and alvo in n.lower() and n not in parecidas]
    if parecidas:
        return "", ("Base de Conhecimento não encontrada: "
                    f"'{nome}'. Parecidas: {', '.join(parecidas[:10])}. "
                    "Pergunte ao técnico qual delas.")
    return "", (f"Base de Conhecimento não encontrada: '{nome}'. Use "
                "listar_bases_conhecimento para ver as cadastradas.")


def _lista_curta(itens: list[str], limite: int = 12) -> str:
    if len(itens) <= limite:
        return ", ".join(itens)
    return ", ".join(itens[:limite]) + f" … (+{len(itens) - limite})"


def _ok_falha(ok: bool) -> str:
    return "✅" if ok else "❌"


# --------------------------------------------------------------------------- #
# Bases de Conhecimento (local)
# --------------------------------------------------------------------------- #

def _local_bases(args: dict) -> str:
    nomes = _nomes_bases()
    filtro = (args.get("filtro") or "").strip()
    if filtro:
        nomes = _bases_por_palavras(filtro)
    if not nomes:
        return "Nenhuma base encontrada."
    return "Bases cadastradas: " + "; ".join(nomes[:80])


# --------------------------------------------------------------------------- #
# Desmembramento — Criar + Base / Só Criar
# --------------------------------------------------------------------------- #

MARCADOR_TOMBO = "{{tombo}}"


def _prep_desmembrar(args: dict) -> "Acao | str":
    from bot.services import desmembramento_service as ds

    pai = str(args.get("chamado_pai") or "").strip()
    tombos = _lista(args.get("tombos"))
    descricao = (args.get("descricao") or "").strip()
    if not pai:
        return "Falta o número do chamado pai. Pergunte ao técnico."
    if not tombos:
        return "Falta a lista de tombos (um filho por tombo). Pergunte ao técnico."
    if not descricao:
        return ("Falta a descrição dos chamados filhos. Pergunte ao técnico "
                "qual texto usar.")
    if MARCADOR_TOMBO not in descricao:
        descricao = f"{descricao} Tombo: {MARCADOR_TOMBO}"

    base = ""
    if args.get("base"):
        base, erro = _resolver_base(args["base"])
        if erro:
            return erro

    sit = ds.situacao(pai)
    linhas = [
        f"**Modo:** {'Criar + Base' if base else 'Só Criar'}",
        f"**Chamado pai:** {pai}",
        f"**Filhos:** {len(tombos)} (tombos {_lista_curta(tombos)})",
    ]
    if base:
        linhas.append(f"**Base:** {base}")
    linhas.append(f"**Descrição (1º filho):** {descricao.replace(MARCADOR_TOMBO, tombos[0])}")
    return Acao(
        ferramenta="desmembrar",
        args={"chamado_pai": pai, "tombos": tombos, "descricao": descricao, "base": base},
        titulo="Desmembramento",
        linhas=linhas,
        escreve=True,
        checkpoint=sit["estado"],
        aviso=sit.get("resumo", ""),
    )


def _kb_config(nome_base: str) -> dict:
    from services import kb_store
    e = next(e for e in kb_store.carregar() if e["nome_artigo"] == nome_base)
    return {"keyword": e["keyword"], "nome_artigo": e["nome_artigo"]}


def _exec_desmembrar(a: dict, s: Sessao) -> Resultado:
    """As mesmas classes que a página de Desmembramento usa, na página da
    sessão do plano. O login delas vê a sessão ativa e segue."""
    import pandas as pd
    from services import checkpoint
    from services.flow_desmembramento_pw import FluxoCompletoPW, FluxoCriarPW
    from services.kb_manager_pw import executar_kb_unica_pw

    pai, tombos = a["chamado_pai"], a["tombos"]
    df = pd.DataFrame([[t] for t in tombos], columns=["tombo"])
    page = s.pagina()
    if a["base"]:
        kb = _kb_config(a["base"])
        FluxoCompletoPW(page, s.matricula, s.senha, s.log, origem="ui").executar(
            df=df, descricao_base=a["descricao"], numero_chamado=pai,
            kb_function=lambda p, l: executar_kb_unica_pw(p, l, kb, voltar_ao_evento=True),
            iniciar_do_zero=s.iniciar_do_zero)
    else:
        FluxoCriarPW(page, s.matricula, s.senha, s.log, origem="ui").executar(
            df=df, descricao_base=a["descricao"], numero_chamado=pai,
            iniciar_do_zero=s.iniciar_do_zero)

    # O fluxo não devolve nada: o relato sai do checkpoint (como no bot).
    estados = {l["index"]: l for l in checkpoint.status_linhas(pai)}
    feitos = 0
    linhas = []
    for i, tombo in enumerate(tombos):
        l = estados.get(i, {})
        feito = l.get("status") == "concluido"
        feitos += feito
        extra = "" if feito else f" ({l.get('status', 'pendente')})"
        linhas.append(f"- {_ok_falha(feito)} tombo {tombo} → **{l.get('numero_filho') or '—'}**{extra}")
    cab = f"**Desmembramento de {pai}** — {feitos} de {len(tombos)} concluído(s)."
    return Resultado("\n".join([cab] + linhas), ok=feitos == len(tombos))


# --------------------------------------------------------------------------- #
# Desmembramento — Só Base
# --------------------------------------------------------------------------- #

def _prep_aplicar_base(args: dict) -> "Acao | str":
    from bot.services import desmembramento_service as ds

    chamados = _lista(args.get("chamados"))
    if not chamados:
        return "Falta a lista de chamados onde aplicar a base."
    if not args.get("base"):
        return "Falta o nome da Base de Conhecimento."
    base, erro = _resolver_base(args["base"])
    if erro:
        return erro
    sit = ds.situacao(ds.chave_bc(chamados))
    return Acao(
        ferramenta="aplicar_base",
        args={"chamados": chamados, "base": base},
        titulo="Aplicar Base (Só Base)",
        linhas=[f"**Base:** {base}",
                f"**Chamados:** {len(chamados)} ({_lista_curta(chamados)})"],
        escreve=True,
        checkpoint=sit["estado"],
        aviso=sit.get("resumo", ""),
    )


def _exec_aplicar_base(a: dict, s: Sessao) -> Resultado:
    from services import checkpoint
    from services.flow_desmembramento_pw import FluxoBCPW, _chave_checkpoint
    from services.kb_manager_pw import executar_kb_unica_pw

    kb = _kb_config(a["base"])
    FluxoBCPW(s.pagina(), s.matricula, s.senha, s.log, origem="ui").executar(
        filhos=a["chamados"],
        kb_function=lambda p, l: executar_kb_unica_pw(p, l, kb, voltar_ao_evento=False),
        iniciar_do_zero=s.iniciar_do_zero)
    por_indice = {l["index"]: l["status"]
                  for l in checkpoint.status_linhas(_chave_checkpoint(a["chamados"]))}
    feitos = 0
    linhas = []
    for i, c in enumerate(a["chamados"]):
        st = por_indice.get(i, "pendente")
        feitos += st == "concluido"
        linhas.append(f"- {_ok_falha(st == 'concluido')} {c}" + ("" if st == "concluido" else f" ({st})"))
    cab = f"**Base {a['base']}** — {feitos} de {len(a['chamados'])} chamado(s)."
    return Resultado("\n".join([cab] + linhas), ok=feitos == len(a["chamados"]))


# --------------------------------------------------------------------------- #
# Requisição de Serviço
# --------------------------------------------------------------------------- #

def _texto_requisicoes(reqs: list[dict]) -> str:
    """O MESMO texto que o técnico colaria na página — assim a chave do
    checkpoint (hash do texto) é a mesma pela página e pelo Assistente."""
    return "\n".join(
        SEPARADOR.join(str(r.get(c) or "").strip() for c in ORDEM_COLUNAS)
        for r in reqs
    )


def _prep_requisicoes(args: dict) -> "Acao | str":
    from services import checkpoint
    from services.flow_requisicao_pw import _chave_checkpoint, parse_entrada

    reqs = args.get("requisicoes") or []
    if not reqs:
        return "Falta a lista de requisições."
    for i, r in enumerate(reqs, 1):
        for c in ORDEM_COLUNAS:
            if SEPARADOR in str(r.get(c) or ""):
                return (f"Requisição {i}: o campo {POR_CHAVE[c].rotulo} contém "
                        f"'{SEPARADOR}', que não é permitido. Reescreva sem ele.")
        if not str(r.get("usuario_afetado") or "").strip():
            return f"Requisição {i}: falta o Usuário afetado (matrícula)."
        if not str(r.get("item") or "").strip():
            return f"Requisição {i}: falta o Item."
    texto = _texto_requisicoes(reqs)
    try:
        parse_entrada(texto)
    except ValueError as e:
        return f"Entrada inválida: {e}"

    chave = _chave_checkpoint(texto)
    estado = "novo"
    aviso = ""
    if checkpoint.esta_corrompido(chave):
        estado = "corrompido"
    elif checkpoint.foi_concluido(chave):
        estado, aviso = "concluido", "Este lote já foi criado antes — nada a fazer."
    elif checkpoint.existe_pendente(chave):
        estado, aviso = "pendente", "Lote já começado: " + checkpoint.resumo(chave)

    linhas = [f"**Requisições:** {len(reqs)}", _bloco_lista(texto)]
    return Acao(
        ferramenta="criar_requisicoes",
        args={"texto": texto},
        titulo="Requisição de Serviço",
        linhas=linhas,
        escreve=True,
        pode_simular=True,
        checkpoint=estado,
        aviso=aviso,
        copiar=texto,
    )


def _bloco_lista(texto: str) -> str:
    """A lista COMPLETA no cartão (pedido de 06/10), para o técnico conferir
    linha a linha — antes o cartão mostrava só um resumo."""
    return f"**Lista completa** (é esta que será criada):\n```\n{texto}\n```"


def requisicoes_coladas(mensagem: str) -> "Acao | None":
    """O técnico colou no chat uma lista de requisições (a do botão "Copiar
    lista")? Então o cartão sai DESTA lista, sem passar pela IA.

    Por quê (06/10): ao pedir "gere a lista de novo", a IA reescreveu o lote
    com alguma diferença, a chave do checkpoint (hash do texto) mudou e 2
    requisições foram criadas em dobro. Colada, a lista é a mesma -> mesma
    chave -> retoma de onde parou.

    Só reconhece se TODAS as linhas não vazias tiverem as colunas completas,
    como o cartão gera: mensagem com outro texto junto vai para a IA, que
    pode ter instrução nova ("troque o técnico").
    """
    from services.flow_requisicao_pw import parse_entrada

    # Cercas ``` coladas junto com a lista não contam como texto.
    linhas = [l for l in mensagem.splitlines() if l.strip().strip("`")]
    n = len(ORDEM_COLUNAS) - 1
    if not linhas or any(l.count(SEPARADOR) != n for l in linhas):
        return None
    try:
        reqs = parse_entrada("\n".join(linhas))
    except ValueError:
        return None
    r = _prep_requisicoes({"requisicoes": reqs})
    return r if isinstance(r, Acao) else None


def _exec_requisicoes(a: dict, s: Sessao) -> Resultado:
    """Mesmo laço do state/requisicao_state.py, com o mesmo checkpoint: se
    parar no meio, rodar de novo (aqui ou na página) continua de onde parou.
    No modo simulação o checkpoint não é tocado — nada foi criado."""
    from services import checkpoint as cp
    from services.flow_requisicao_pw import (
        _chave_checkpoint, criar_requisicao, parse_entrada,
    )

    modo_teste, log = s.modo_teste, s.log
    texto = a["texto"]
    reqs = parse_entrada(texto)
    total = len(reqs)
    chave = _chave_checkpoint(texto)
    feitas = {}
    if not modo_teste:
        if cp.foi_concluido(chave):
            return Resultado("Este lote já foi criado antes — nada a fazer.")
        if cp.existe_pendente(chave):
            feitas = {l["index"]: l for l in cp.status_linhas(chave)
                      if l["status"] == cp.STATUS_CONCLUIDO}
        else:
            cp.inicializar(chave, total, fluxo="requisicao", origem="ui",
                           matricula=s.matricula,
                           referencias=[r.get("usuario_afetado", "") for r in reqs])

    resultado = []
    page = s.pagina()
    if True:  # (mantém o recuo do laço original)
        for i, valores in enumerate(reqs):
            if i in feitas:
                resultado.append(f"- ✅ {i + 1}. **{feitas[i].get('numero', '')}** (já criada antes)")
                continue
            log(f"Requisição {i + 1} de {total}...", "status")
            try:
                criada = criar_requisicao(page, log, valores, modo_teste)
            except Exception as e:
                criada, erro = None, str(e)
            else:
                erro = "o fluxo não concluiu"
            if criada is None:
                resultado.append(f"- ❌ {i + 1}. falhou ({erro})")
                continue
            if modo_teste:
                resultado.append(f"- ✅ {i + 1}. preenchida (simulação, não salva)")
                continue
            cp.marcar_concluido_linha(chave, i, numero=criada.numero, usuario=criada.usuario)
            resultado.append(f"- ✅ {i + 1}. **{criada.numero}** — {criada.usuario}")

    ok = sum(1 for l in resultado if l.startswith("- ✅"))
    cab = "**Simulação da Requisição**" if modo_teste else "**Requisição de Serviço**"
    rodape = [] if ok == total or modo_teste else [
        "\nPara tentar as que faltaram, peça de novo o mesmo lote: ele continua de onde parou."]
    return Resultado("\n".join([f"{cab} — {ok} de {total}."] + resultado + rodape),
                     ok=ok == total)


# --------------------------------------------------------------------------- #
# Requisição por tombo — as "regras de negócio" (2026-10-01)
# --------------------------------------------------------------------------- #
# A IA só identifica o TIPO do pedido e extrai os dados; o código expande uma
# linha por tombo, normaliza o tombo e confere os nomes. Pedir à IA que
# escrevesse cada requisição inteira falhou com listas grandes (30/09).

def normalizar_tombo(t: str) -> str:
    """'FCBVCUSTO265287' -> '265287'; '*333284' -> '333284'. Regra do usuário:
    o tombo são os 6 últimos dígitos do código da máquina."""
    numeros = re.findall(r"\d+", str(t))
    if not numeros:
        raise ValueError(f"Tombo sem número: '{t}'.")
    ultimo = numeros[-1]
    return ultimo[-6:] if len(ultimo) >= 6 else ultimo


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                   if unicodedata.category(c) != "Mn")


def _resolver_nome(valor: str, opcoes: list[str], rotulo: str) -> tuple[str, str]:
    """(nome_cadastrado, erro). Aceita parte do nome ('Arthur' -> o nome
    completo) se só UM cadastrado bater; ambíguo ou desconhecido vira
    pergunta, nunca chute."""
    alvo = _sem_acento(valor or "").strip()
    if not alvo:
        return "", f"Falta {rotulo}. Pergunte ao técnico."
    for o in opcoes:
        if _sem_acento(o) == alvo:
            return o, ""
    palavras = alvo.split()
    batem = [o for o in opcoes if all(p in _sem_acento(o) for p in palavras)]
    if len(batem) == 1:
        return batem[0], ""
    if len(batem) > 1:
        return "", (f"{rotulo} '{valor}' é ambíguo: {', '.join(batem)}. "
                    "Pergunte qual.")
    return "", (f"{rotulo} '{valor}' não está cadastrado. Cadastrados: "
                f"{', '.join(opcoes)}. Pergunte ao técnico qual é (ou peça para "
                "cadastrar em Configurações -> Presets).")


def _opcoes() -> dict[str, list[str]]:
    from services import requisicao_presets
    p = requisicao_presets.carregar()
    filas = list(dict.fromkeys(p["grupo_atribuido"] + list(FILAS)))
    return {"tecnicos": p["usuario_atribuido"], "filas": filas,
            "edificios": p["edificio"], "itens": p["item"]}


def _desc_por_tombo() -> str:
    o = _opcoes()
    return (
        "Abre Requisições de Serviço, uma por tombo (o sistema monta cada uma). "
        "Use para pedidos com tombos ou de um tipo de solicitação da base."
        # Técnicos e filas saíram (06/10): o código resolve nome parcial e,
        # se ambíguo/desconhecido, devolve as opções para o modelo perguntar.
        # Edifícios ficam: nome fora dos Presets não trava, só avisa.
        + f"\nEdifícios: {', '.join(o['edificios'])}."
    )


def _prep_por_tombo(args: dict) -> "Acao | str":
    from services.agente import conhecimento

    matricula = str(args.get("matricula") or "").strip()
    if not matricula:
        return "Falta a matrícula do usuário afetado. Pergunte ao técnico."
    o = _opcoes()
    tecnico, erro = _resolver_nome(args.get("tecnico", ""), o["tecnicos"], "O técnico")
    if erro:
        return erro
    fila, erro = _resolver_nome(args.get("fila", ""), o["filas"], "A fila")
    if erro:
        return erro
    if not str(args.get("edificio") or "").strip():
        return "Falta o edifício. Pergunte ao técnico."
    # Edifício e Item não travam se não estiverem nos Presets (a lista ainda é
    # curta): usa o cadastrado quando bate e, senão, segue com aviso no cartão.
    avisos = []
    edificio, erro = _resolver_nome(args["edificio"], o["edificios"], "O edifício")
    if erro:
        edificio = args["edificio"].strip()
        avisos.append(f"Edifício '{edificio}' não está nos Presets.")

    tipo = None
    if args.get("tipo"):
        tipo = next((t for t in conhecimento.tipos()
                     if _sem_acento(t.nome) == _sem_acento(args["tipo"])), None)
    item = (args.get("item") or (tipo.item if tipo else "")).strip()
    if not item:
        return "Não consegui deduzir o Item. Pergunte ao técnico."
    item_ok, erro = _resolver_nome(item, o["itens"], "O item")
    if erro:
        avisos.append(f"Item '{item}' não está nos Presets.")
    else:
        item = item_ok
    categoria = (args.get("categoria") or (tipo.categoria if tipo else "Configuração")).strip()
    resumo = (args.get("resumo") or (tipo.resumo if tipo else "Requisição de Serviço")).strip()
    modelo = (args.get("descricao") or (tipo.descricao if tipo else "")).strip()
    if not modelo:
        return "Falta a descrição do pedido. Pergunte ao técnico."

    try:
        tombos = [normalizar_tombo(t) for t in _lista(args.get("tombos"))]
    except ValueError as e:
        return str(e)
    tombos = list(dict.fromkeys(tombos))
    if tombos and "{tombo}" not in modelo:
        modelo = modelo.rstrip(".") + ". Tombo: {tombo}."

    def linha(tombo: str = "") -> dict:
        return {
            "usuario_afetado": matricula, "edificio": edificio, "resumo": resumo,
            "descricao": modelo.replace("{tombo}", tombo).replace("{edificio}", edificio),
            "item": item, "item_b": f"*{tombo}" if tombo else "",
            "categoria": categoria, "grupo_atribuido": fila,
            "usuario_atribuido": tecnico,
        }
    reqs = [linha(t) for t in tombos] or [linha()]

    base = _prep_requisicoes({"requisicoes": reqs})
    if isinstance(base, str):
        return base
    base.titulo = f"Requisição de Serviço{f' — {tipo.nome}' if tipo else ''}"
    base.linhas = [
        f"**Requisições:** {len(reqs)}"
        + (f" (uma por tombo: {_lista_curta(tombos)})" if tombos else ""),
        f"**Usuário afetado:** {matricula} · **Edifício:** {edificio}",
        f"**Item:** {item} · **Categoria:** {categoria} · **Resumo:** {resumo}",
        f"**Fila:** {fila} · **Técnico:** {tecnico}",
        _bloco_lista(base.copiar),
    ]
    base.aviso = " ".join(avisos + ([base.aviso] if base.aviso else []))
    return base


# --------------------------------------------------------------------------- #
# Ações em lote nos chamados (Atendimento, Informação, Fornecedor, Usuário)
# --------------------------------------------------------------------------- #

def _prep_lote(nome: str, titulo: str, com_texto: bool):
    def preparar(args: dict) -> "Acao | str":
        chamados = _lista(args.get("chamados"))
        if not chamados:
            return "Falta a lista de chamados."
        texto = (args.get("texto") or "").strip()
        if com_texto and not texto:
            return "Falta o texto a registrar nos chamados. Pergunte ao técnico."
        linhas = [f"**Chamados:** {len(chamados)} ({_lista_curta(chamados)})"]
        if com_texto:
            linhas.append(f"**Texto:** {texto}")
        return Acao(ferramenta=nome, args={"chamados": chamados, "texto": texto},
                    titulo=titulo, linhas=linhas, escreve=True, pode_simular=True)
    return preparar


def _exec_lote(funcao: Callable, titulo: str, com_texto: bool, devolve_info: bool):
    """Mesmo laço dos bot/services/*_service.py, mas na página da sessão."""
    def executar(a: dict, s: Sessao) -> Resultado:
        page = s.pagina()
        r = {}
        for numero in a["chamados"]:
            s.log(f"{titulo}: chamado {numero}...", "status")
            try:
                if com_texto:
                    saida = funcao(page, s.log, numero, a["texto"], s.modo_teste)
                else:
                    saida = funcao(page, s.log, numero, modo_teste=s.modo_teste)
                ok = saida[0] if devolve_info else saida
                r[numero] = (ok, "" if ok else "o fluxo não chegou ao fim")
            except Exception as e:  # um chamado não derruba os outros
                r[numero] = (False, str(e))
        feitos = sum(1 for v in r.values() if v[0])
        cab = f"**{titulo}{' (simulação, nada salvo)' if s.modo_teste else ''}** — {feitos} de {len(r)}."
        linhas = [cab] + [f"- {_ok_falha(v[0])} {n}" + (f" — {v[1]}" if not v[0] and v[1] else "")
                          for n, v in r.items()]
        return Resultado("\n".join(linhas), ok=feitos == len(r))
    return executar


def _exec_atendimento(a, s):
    from services.flow_atendimento_pw import iniciar_atendimento
    return _exec_lote(iniciar_atendimento, "Iniciar Atendimento", False, False)(a, s)


def _exec_informacao(a, s):
    from services.flow_informacao_pw import adicionar_informacao
    return _exec_lote(adicionar_informacao, "Adicionar Informação", True, True)(a, s)


def _exec_fornecedor(a, s):
    from services.flow_fornecedor_pw import aguardar_info_fornecedor
    return _exec_lote(aguardar_info_fornecedor, "Aguardando Info do Fornecedor", True, True)(a, s)


def _exec_usuario(a, s):
    from services.flow_usuario_pw import aguardar_info_usuario
    return _exec_lote(aguardar_info_usuario, "Aguardando Info do Usuário", True, True)(a, s)


# Retomadas do relógio (06/10): o par de cada pausa — flow_info_recebida_pw.
def _prep_recebida_usuario(args: dict) -> "Acao | str":
    r = _prep_lote("info_recebida_usuario", "Info Recebidas do Usuário", False)(args)
    if isinstance(r, Acao):
        r.linhas.append("**Texto:** Pendência sanada após informações recebida do(a) "
                        "senhor(a) **NOME** (lido de cada chamado), atendimento retomado.")
    return r


def _exec_recebida_usuario(a, s):
    from services.flow_info_recebida_pw import info_recebida_usuario
    return _exec_lote(info_recebida_usuario, "Info Recebidas do Usuário", False, True)(a, s)


def _exec_recebida_fornecedor(a, s):
    from services.flow_info_recebida_pw import info_recebida_fornecedor
    return _exec_lote(info_recebida_fornecedor, "Info Recebida do Fornecedor", True, True)(a, s)


# --------------------------------------------------------------------------- #
# Configurar filas (06/10) — consulta salva do monitor; não mexe em chamado
# --------------------------------------------------------------------------- #

def _prep_config_filas(args: dict) -> "Acao | str":
    from services.flow_config_fila_pw import COLUNAS_PADRAO, PERFIL_PADRAO
    filas = [f.strip() for f in (args.get("filas") or []) if str(f).strip()]
    if not filas:
        return "Falta a lista de filas a configurar."
    if not COLUNAS_PADRAO:
        return "As colunas padrão do perfil ainda não foram definidas no sistema."
    return Acao(ferramenta="configurar_filas", args={"filas": filas},
                titulo="Configurar filas",
                linhas=[f"**Filas:** {len(filas)} ({_lista_curta(filas)})",
                        f"**Perfil de coluna:** {PERFIL_PADRAO} (criado na 1ª vez, "
                        "com as colunas padrão; depois reaproveitado)",
                        "*Código, Nome e Departamento = o nome de cada fila.*"],
                escreve=True, pode_simular=True)


def _exec_config_filas(a, s: Sessao) -> Resultado:
    """Perfil primeiro (garantir_perfil: cria ou reaproveita); sem ele as
    filas não têm o que usar, então a falha dele para tudo."""
    from services.flow_config_fila_pw import PERFIL_PADRAO, configurar_fila, garantir_perfil
    page = s.pagina()
    s.log(f"Conferindo o Perfil de coluna {PERFIL_PADRAO}...", "status")
    try:
        perfil = garantir_perfil(page, s.log, s.modo_teste)
    except Exception as e:
        perfil = None
        s.log(f"Erro no Perfil de coluna: {e}", "error")
    if perfil is None:
        return Resultado(f"❌ **Perfil de coluna {PERFIL_PADRAO}** falhou — nenhuma "
                         "fila foi configurada. Veja o log.", ok=False)
    estado = {"existente": "já existia", "criado": "criado",
              "simulado": "seria criado"}[perfil]
    feitos, linhas = 0, [f"- ✅ Perfil de coluna **{PERFIL_PADRAO}** ({estado})"]
    for fila in a["filas"]:
        s.log(f"Configurando a fila {fila}...", "status")
        try:
            ok = configurar_fila(page, s.log, fila, PERFIL_PADRAO, s.modo_teste,
                                 perfil_novo=perfil == "simulado")
            erro = "" if ok else " — o fluxo não chegou ao fim"
        except Exception as e:  # uma fila não derruba as outras
            ok, erro = False, f" — {e}"
        feitos += ok
        linhas.append(f"- {_ok_falha(ok)} {fila}{erro}")
    sufixo = " (simulação, nada salvo)" if s.modo_teste else ""
    cab = f"**Configurar filas{sufixo}** — {feitos} de {len(a['filas'])}."
    return Resultado("\n".join([cab] + linhas), ok=feitos == len(a["filas"]))


# --------------------------------------------------------------------------- #
# Atendimento Programado
# --------------------------------------------------------------------------- #

def _prep_programar(args: dict) -> "Acao | str":
    from services.flow_programar_pw import normalizar_dia, normalizar_hora

    chamados = _lista(args.get("chamados"))
    if not chamados:
        return "Falta o número do chamado."
    motivo = (args.get("motivo") or "").strip()
    if not args.get("dia") or not args.get("hora"):
        return "Falta o dia (dd/mm) e/ou a hora (hh:mm) do atendimento. Pergunte ao técnico."
    if not motivo:
        return "Falta o motivo da programação. Pergunte ao técnico."
    try:
        dia, hora = normalizar_dia(args["dia"]), normalizar_hora(args["hora"])
    except ValueError as e:
        return str(e)
    return Acao(
        ferramenta="programar_atendimento",
        args={"chamados": chamados, "dia": dia, "hora": hora, "motivo": motivo},
        titulo="Atendimento Programado",
        linhas=[f"**Chamados:** {len(chamados)} ({_lista_curta(chamados)})",
                f"**Quando:** {dia} às {hora}",
                f"**Motivo:** {motivo}",
                "*O nome do usuário afetado é lido de cada chamado.*"],
        escreve=True,
        pode_simular=True,
    )


def _exec_programar(a, s: Sessao) -> Resultado:
    from services.flow_programar_pw import programar_atendimento
    page = s.pagina()
    feitos, linhas = 0, []
    for numero in a["chamados"]:
        s.log(f"Programando atendimento do chamado {numero}...", "status")
        try:
            ok, info = programar_atendimento(page, s.log, numero, a["dia"], a["hora"],
                                             a["motivo"], s.modo_teste)
            erro = "" if ok else " (o fluxo não chegou ao fim)"
        except Exception as e:
            ok, info, erro = False, {}, f" ({e})"
        feitos += ok
        quem = f" — {info['usuario']}" if info.get("usuario") else ""
        linhas.append(f"- {_ok_falha(ok)} {numero}{quem}{erro}")
    sufixo = " (simulação, nada salvo)" if s.modo_teste else ""
    cab = (f"**Atendimento Programado{sufixo}** — {feitos} de {len(a['chamados'])}, "
           f"para {a['dia']} às {a['hora']}.")
    return Resultado("\n".join([cab] + linhas), ok=feitos == len(a["chamados"]))


# --------------------------------------------------------------------------- #
# Só leitura — Minha Fila e SLA
# --------------------------------------------------------------------------- #

def _prep_fila(args: dict) -> "Acao | str":
    return Acao(ferramenta="consultar_minha_fila", args={}, titulo="Minha Fila",
                linhas=[], escreve=False)


def _exec_fila(a, s: Sessao) -> Resultado:
    from services.flow_minhafila_pw import ler_fila
    fila = ler_fila(s.pagina(), s.log)
    if fila is None:
        return Resultado("❌ Não consegui ler a sua fila (a tela não carregou).", ok=False)
    if not fila:
        return Resultado("Sua fila está vazia.")
    linhas = [f"**Sua fila** — {len(fila)} chamado(s):"]
    for c in fila:
        linhas.append(f"- **{c.get('referencia', '')}** — {c.get('afetado', '')} · {c.get('secao', '')}")
    return Resultado("\n".join(linhas))


def _prep_sla(args: dict) -> "Acao | str":
    chamados = _lista(args.get("chamados"))
    if not chamados:
        return "Falta a lista de chamados para analisar."
    fila = args.get("fila") or FILA_PADRAO
    if fila not in FILAS:
        return f"Fila desconhecida: '{fila}'. Filas válidas: {', '.join(FILAS)}."
    return Acao(ferramenta="analisar_sla", args={"chamados": chamados, "fila": fila},
                titulo="Análise de SLA", linhas=[], escreve=False)


def _exec_sla(a, s: Sessao) -> Resultado:
    """Mesmo laço do bot/services/sla_service.py, na página da sessão."""
    from services.browser_pw import _usuario_afetado_pw
    from services.flow_sla_pw import extrair_historico_chamado
    from services.sla_engine import calcular_sla

    page = s.pagina()
    linhas = [f"**SLA — fila {a['fila']}**"]
    todos_ok = True
    for numero in a["chamados"]:
        s.log(f"Analisando o SLA de {numero}...", "status")
        historico = extrair_historico_chamado(page, numero, s.log)
        if historico is None:
            todos_ok = False
            linhas.append(f"- ❌ {numero} — não consegui abrir o chamado ou ler o histórico")
            continue
        _usuario_afetado_pw(page)  # garante a tela do chamado (como no bot)
        r = calcular_sla(historico, a["fila"])
        icone = "🔴" if r.get("estourado") else "🟢"
        linhas.append(f"- {icone} **{numero}** — {r.get('mensagem', '--')} "
                      f"(gasto {r.get('tempo_gasto_str', '--')}, resta "
                      f"{r.get('tempo_restante_str', '--')})")
    return Resultado("\n".join(linhas), ok=todos_ok)


# --------------------------------------------------------------------------- #
# Resolver chamado (2026-10-01)
# --------------------------------------------------------------------------- #

def _prep_resolver(args: dict) -> "Acao | str":
    chamados = _lista(args.get("chamados"))
    if not chamados:
        return "Falta o número do chamado."
    procedimentos = (args.get("procedimentos") or "").strip()
    if not procedimentos:
        return "Faltam os procedimentos realizados (vão no texto da resolução). Pergunte."
    fila = args.get("fila") or FILA_PADRAO
    if fila not in FILAS:
        return f"Fila desconhecida: '{fila}'. Filas válidas: {', '.join(FILAS)}."
    return Acao(
        ferramenta="resolver_chamado",
        args={"chamados": chamados, "procedimentos": procedimentos, "fila": fila},
        titulo="Resolver chamado",
        linhas=[f"**Chamados:** {len(chamados)} ({_lista_curta(chamados)})",
                f"**Procedimentos:**\n{procedimentos}"],
        escreve=True,
        pode_simular=True,
    )


def _exec_resolver(a, s: Sessao) -> Resultado:
    from services.flow_resolver_pw import resolver_chamado
    page = s.pagina()
    feitos, linhas = 0, []
    for numero in a["chamados"]:
        s.log(f"Resolvendo o chamado {numero}...", "status")
        try:
            ok, info = resolver_chamado(page, s.log, numero, a["procedimentos"],
                                        a["fila"], s.modo_teste)
        except Exception as e:
            ok, info = False, {"erro": str(e)}
        feitos += ok
        if info.get("estourado"):
            motivo = f" — NÃO resolvido: SLA {info['sla']}"
        elif not ok:
            motivo = f" — {info.get('erro', 'o fluxo não chegou ao fim')}"
        else:
            motivo = f" — {info.get('usuario', '')}"
        linhas.append(f"- {_ok_falha(ok)} {numero}{motivo}")
    sufixo = " (simulação, nada salvo)" if s.modo_teste else ""
    cab = f"**Resolver chamado{sufixo}** — {feitos} de {len(a['chamados'])}."
    return Resultado("\n".join([cab] + linhas), ok=feitos == len(a["chamados"]))


# --------------------------------------------------------------------------- #
# Investigação — leituras cujo resultado volta para a IA (2026-10-01)
# --------------------------------------------------------------------------- #

def _inv_buscar_chamado(args: dict, s: Sessao) -> str:
    """Acha o chamado pelo NOME do usuário (e setor) na fila do técnico — os
    técnicos lembram de "o chamado da Carla", não do número. A comparação é
    feita aqui no código; para a IA só vão os chamados que BATEM com o nome
    que o próprio técnico citou, nunca a fila inteira."""
    from services.flow_minhafila_pw import ler_fila

    nome = _sem_acento(args.get("nome") or "").strip()
    setor = _sem_acento(args.get("setor") or "").strip()
    if not nome:
        return "Falta o nome do usuário para procurar."
    fila = ler_fila(s.pagina(), s.log)
    if fila is None:
        return "Não consegui ler a fila do técnico (a tela não carregou)."
    batem = [c for c in fila
             if all(p in _sem_acento(c.get("afetado", "")) for p in nome.split())
             and (not setor or all(p in _sem_acento(c.get("secao", "")) for p in setor.split()))]
    if not batem:
        return (f"Nenhum chamado de '{args.get('nome')}' na fila do técnico "
                f"({len(fila)} chamados na fila). Pergunte o número do chamado.")
    linhas = [f"{c['referencia']} — {c.get('afetado', '')} ({c.get('secao', '')})" for c in batem]
    if len(batem) == 1:
        return "Encontrado 1 chamado: " + linhas[0]
    return (f"{len(batem)} chamados batem com '{args.get('nome')}': " + "; ".join(linhas)
            + ". Pergunte ao técnico qual (mostre nome e setor).")


def _inv_verificar_sla(args: dict, s: Sessao) -> str:
    """SLA para a IA DECIDIR: só número, fila e tempo — nada do usuário."""
    from services.flow_sla_pw import extrair_historico_chamado
    from services.sla_engine import calcular_sla

    chamados = _lista(args.get("chamados"))
    if not chamados:
        return "Falta o número do chamado."
    fila = args.get("fila") or FILA_PADRAO
    if fila not in FILAS:
        return f"Fila desconhecida: '{fila}'. Filas válidas: {', '.join(FILAS)}."
    saida = []
    for numero in chamados:
        historico = extrair_historico_chamado(s.pagina(), numero, s.log)
        if historico is None:
            saida.append(f"{numero}: não consegui ler o histórico")
            continue
        r = calcular_sla(historico, fila)
        situacao = "ESTOURADO" if r.get("estourado") else "NO PRAZO"
        saida.append(f"{numero}: {situacao} — {r.get('mensagem', '')} (fila {fila})")
    return "; ".join(saida)


# --------------------------------------------------------------------------- #
# Catálogo
# --------------------------------------------------------------------------- #

# ENXUTO DE PROPÓSITO (06/10): estes esquemas vão em TODA ida ao modelo
# (~5.200 tokens por ida antes do enxugamento, 70% deles aqui). Regra de
# negócio NÃO entra aqui: mora em conhecimento/*.md (fonte única). Aqui só o
# que a ferramenta faz e o formato dos campos.
_CHAMADOS = {"type": "array", "items": {"type": "string"}}
# A fila é conferida no código (erro devolve as válidas) — sem `enum` aqui.
_FILA = {"type": "string", "description": "Fila do SLA."}

FERRAMENTAS: dict[str, Ferramenta] = {f.nome: f for f in [
    Ferramenta(
        "buscar_chamado_por_usuario",
        "INVESTIGAÇÃO: acha o chamado na fila do técnico pelo nome do usuário afetado.",
        {"type": "object", "properties": {
            "nome": {"type": "string"},
            "setor": {"type": "string"},
        }, "required": ["nome"]},
        preparar=lambda a: "", investiga=_inv_buscar_chamado,
    ),
    Ferramenta(
        "resolver_chamado",
        "Resolve o chamado (ação 'Resolvido'); o sistema monta o texto da auditoria.",
        {"type": "object", "properties": {
            "chamados": _CHAMADOS,
            "procedimentos": {"type": "string", "description":
                "Ditos pelo técnico, no formato de Procedimentos da base."},
            "fila": _FILA,
        }, "required": ["chamados", "procedimentos"]},
        preparar=_prep_resolver, executar=_exec_resolver,
    ),
    Ferramenta(
        "verificar_sla",
        "INVESTIGAÇÃO: diz se o chamado está NO PRAZO ou ESTOURADO e quanto resta.",
        {"type": "object", "properties": {
            "chamados": _CHAMADOS,
            "fila": _FILA,
        }, "required": ["chamados"]},
        preparar=lambda a: "", investiga=_inv_verificar_sla,
    ),
    Ferramenta(
        "listar_bases_conhecimento",
        "Lista as Bases de Conhecimento cadastradas (filtro: palavras do nome).",
        {"type": "object", "properties": {"filtro": {"type": "string"}}},
        preparar=lambda a: "", local=_local_bases,
    ),
    Ferramenta(
        "desmembrar",
        "Cria um chamado filho por tombo a partir do pai; com 'base', aplica a "
        "base em cada filho.",
        {"type": "object", "properties": {
            "chamado_pai": {"type": "string"},
            "tombos": {"type": "array", "items": {"type": "string"}},
            "descricao": {"type": "string", "description":
                          "Dos filhos. {{tombo}} onde entra o tombo (sem ele, vai no fim)."},
            "base": {"type": "string", "description": "Nome ou palavras da base."},
        }, "required": ["chamado_pai", "tombos", "descricao"]},
        preparar=_prep_desmembrar, executar=_exec_desmembrar,
    ),
    Ferramenta(
        "aplicar_base",
        "Aplica uma Base de Conhecimento em chamados que já existem.",
        {"type": "object", "properties": {
            "chamados": _CHAMADOS,
            "base": {"type": "string", "description": "Nome ou palavras da base."},
        }, "required": ["chamados", "base"]},
        preparar=_prep_aplicar_base, executar=_exec_aplicar_base,
    ),
    Ferramenta(
        "criar_requisicoes",
        "Abre Requisições de Serviço, uma por item da lista (campos repetidos "
        "em cada item; nenhum com ';'). Pedido com tombos: use "
        "criar_requisicoes_por_tombo.",
        {"type": "object", "properties": {"requisicoes": {"type": "array", "items": {
            "type": "object", "properties": {
                "usuario_afetado": {"type": "string", "description": "Matrícula."},
                "edificio": {"type": "string"},
                "resumo": {"type": "string"},
                "descricao": {"type": "string"},
                "item": {"type": "string"},
                "item_b": {"type": "string"},
                "categoria": {"type": "string"},
                "grupo_atribuido": {"type": "string"},
                "usuario_atribuido": {"type": "string", "description": "Técnico."},
            }, "required": ["usuario_afetado", "item"]}}},
         "required": ["requisicoes"]},
        preparar=_prep_requisicoes, executar=_exec_requisicoes,
    ),
    Ferramenta(
        "criar_requisicoes_por_tombo",
        _desc_por_tombo,  # montada na hora: lê tipos e nomes do banco
        {"type": "object", "properties": {
            "matricula": {"type": "string", "description": "Do usuário afetado."},
            "edificio": {"type": "string"},
            "fila": {"type": "string", "description": "Grupo atribuído."},
            "tecnico": {"type": "string", "description": "Técnico atribuído (nome ou parte)."},
            "tombos": {"type": "array", "items": {"type": "string"},
                       "description": "Como o técnico escreveu."},
            "tipo": {"type": "string", "description": "Tipo de solicitação da base que bate."},
            "item": {"type": "string", "description": "Só se nenhum tipo bater."},
            "categoria": {"type": "string"},
            "resumo": {"type": "string"},
            "descricao": {"type": "string", "description":
                          "Só se diferente da do tipo. {tombo} onde entra o tombo."},
        }, "required": ["matricula", "edificio", "fila", "tecnico"]},
        preparar=_prep_por_tombo, executar=_exec_requisicoes,
    ),
    Ferramenta(
        "iniciar_atendimento",
        "Inicia o atendimento agora (ação 'Iniciar Atendimento').",
        {"type": "object", "properties": {"chamados": _CHAMADOS}, "required": ["chamados"]},
        preparar=_prep_lote("iniciar_atendimento", "Iniciar Atendimento", False),
        executar=_exec_atendimento,
    ),
    Ferramenta(
        "programar_atendimento",
        "Agenda o atendimento para dia/hora combinados (ação 'Atendimento "
        "Programado'); não é iniciar_atendimento.",
        {"type": "object", "properties": {
            "chamados": _CHAMADOS,
            "dia": {"type": "string", "description": "dd/mm"},
            "hora": {"type": "string", "description": "hh:mm"},
            "motivo": {"type": "string"},
        }, "required": ["chamados", "dia", "hora", "motivo"]},
        preparar=_prep_programar, executar=_exec_programar,
    ),
    Ferramenta(
        "adicionar_informacao",
        "Registra um texto nos chamados (ação 'Adicionar Informação').",
        {"type": "object", "properties": {"chamados": _CHAMADOS, "texto": {"type": "string"}},
         "required": ["chamados", "texto"]},
        preparar=_prep_lote("adicionar_informacao", "Adicionar Informação", True),
        executar=_exec_informacao,
    ),
    Ferramenta(
        "aguardar_fornecedor",
        "PAUSA: 'Aguardando Info do Fornecedor', com um texto.",
        {"type": "object", "properties": {"chamados": _CHAMADOS, "texto": {"type": "string"}},
         "required": ["chamados", "texto"]},
        preparar=_prep_lote("aguardar_fornecedor", "Aguardando Info do Fornecedor", True),
        executar=_exec_fornecedor,
    ),
    Ferramenta(
        "aguardar_usuario",
        "PAUSA: 'Aguardando Info do Usuário' (feito, falta o usuário testar); "
        "o sistema monta o texto da auditoria.",
        {"type": "object", "properties": {"chamados": _CHAMADOS, "texto": {
            "type": "string",
            "description": "Procedimentos ditos pelo técnico, no formato de Procedimentos da base."}},
         "required": ["chamados", "texto"]},
        preparar=_prep_lote("aguardar_usuario", "Aguardando Info do Usuário", True),
        executar=_exec_usuario,
    ),
    Ferramenta(
        "info_recebida_usuario",
        "RETOMADA: 'Info Recebidas do Usuário *' (texto fixo, montado pelo sistema).",
        {"type": "object", "properties": {"chamados": _CHAMADOS},
         "required": ["chamados"]},
        preparar=_prep_recebida_usuario,
        executar=_exec_recebida_usuario,
    ),
    Ferramenta(
        "info_recebida_fornecedor",
        "RETOMADA: 'Info Recebida do Fornecedor', com um texto.",
        {"type": "object", "properties": {"chamados": _CHAMADOS, "texto": {"type": "string"}},
         "required": ["chamados", "texto"]},
        preparar=_prep_lote("info_recebida_fornecedor", "Info Recebida do Fornecedor", True),
        executar=_exec_recebida_fornecedor,
    ),
    Ferramenta(
        "configurar_filas",
        "Configura filas no Assyst (consulta no menu, com o perfil de colunas "
        "padrão). Não mexe em chamados.",
        {"type": "object", "properties": {
            "filas": {"type": "array", "items": {"type": "string"},
                      "description": "Nomes exatos das filas."},
        }, "required": ["filas"]},
        preparar=_prep_config_filas, executar=_exec_config_filas,
    ),
    Ferramenta(
        "consultar_minha_fila",
        "Lista os chamados da fila do técnico (só leitura).",
        {"type": "object", "properties": {}},
        preparar=_prep_fila, executar=_exec_fila,
    ),
    Ferramenta(
        "analisar_sla",
        "Mostra ao técnico o SLA (gasto/restante) dos chamados (só leitura).",
        {"type": "object", "properties": {
            "chamados": _CHAMADOS,
            "fila": _FILA,
        }, "required": ["chamados"]},
        preparar=_prep_sla, executar=_exec_sla,
    ),
]}


def _aceita_null(parametros: dict) -> dict:
    """Campos OPCIONAIS aceitam null. A Groq valida a chamada contra o esquema
    e recusava (erro 400) quando o modelo mandava null num opcional — ex.:
    `setor: null` no buscar_chamado_por_usuario (visto em 01/10)."""
    obrigatorios = set(parametros.get("required", []))
    props = {}
    for nome, p in parametros.get("properties", {}).items():
        if nome not in obrigatorios and isinstance(p.get("type"), str):
            p = {**p, "type": [p["type"], "null"]}
        props[nome] = p
    return {**parametros, "properties": props}


_ULTIMA_ACAO = {
    "type": "boolean",
    # Explicado UMA vez no SISTEMA (vai em ~14 ferramentas; era 180 chars cada).
    "description": "Última ação do pedido?",
}


def _com_ultima_acao(f: Ferramenta, parametros: dict) -> dict:
    """Ferramentas de AÇÃO ganham o campo obrigatório `ultima_acao` (02/10).

    Com ele o modelo diz, já ao pedir o passo, se é o último — e o
    assistente.py não precisa de mais uma ida à IA só para ouvir "acabou" e
    a frase final. Essa ida extra, medida em 02/10, levava ~24 s de um pedido
    de 37 s (estourava o limite de tokens/minuto da Groq)."""
    if f.local or f.investiga or not f.executar:
        return parametros
    return {**parametros,
            "properties": {**parametros.get("properties", {}), "ultima_acao": _ULTIMA_ACAO},
            "required": list(parametros.get("required", [])) + ["ultima_acao"]}


def esquemas() -> list[dict]:
    return [
        {"type": "function", "function": {
            "name": f.nome,
            "description": f.descricao() if callable(f.descricao) else f.descricao,
            "parameters": _aceita_null(_com_ultima_acao(f, f.parametros))}}
        for f in FERRAMENTAS.values()
    ]


def frase_do_plano(acoes: list[Acao]) -> str:
    """'Vou programar o R1 para 03/10 às 14:00 e colocar o R2 aguardando
    fornecedor.' — escrita pelo CÓDIGO a partir do plano (antes era uma ida
    à IA só para isso)."""
    def ch(a):
        c = a.args.get("chamados") or []
        return ", ".join(c) if c else ""
    partes = []
    for a in acoes:
        f = a.ferramenta
        if f == "programar_atendimento":
            partes.append(f"programar o {ch(a)} para {a.args['dia']} às {a.args['hora']}")
        elif f == "resolver_chamado":
            partes.append(f"resolver o {ch(a)}")
        elif f == "aplicar_base":
            partes.append(f"aplicar a base {a.args['base']} no {ch(a)}")
        elif f == "iniciar_atendimento":
            partes.append(f"iniciar o atendimento do {ch(a)}")
        elif f == "aguardar_fornecedor":
            partes.append(f"colocar o {ch(a)} aguardando o fornecedor")
        elif f == "aguardar_usuario":
            partes.append(f"colocar o {ch(a)} aguardando o usuário")
        elif f == "info_recebida_usuario":
            partes.append(f"retomar o {ch(a)} (info recebida do usuário)")
        elif f == "info_recebida_fornecedor":
            partes.append(f"retomar o {ch(a)} (info recebida do fornecedor)")
        elif f == "adicionar_informacao":
            partes.append(f"adicionar a informação no {ch(a)}")
        elif f == "configurar_filas":
            partes.append(f"configurar a(s) fila(s) {', '.join(a.args['filas'])}")
        elif f == "desmembrar":
            partes.append(f"desmembrar o {a.args['chamado_pai']} em "
                          f"{len(a.args['tombos'])} filho(s)")
        elif f == "criar_requisicoes":
            n = len([l for l in a.args.get("texto", "").splitlines() if l.strip()])
            partes.append(f"abrir {n} requisição(ões)")
        else:
            partes.append(a.titulo.lower())
    if not partes:
        return ""
    lista = partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " e " + partes[-1]
    return f"Vou {lista}."


def executar(acao: Acao, sessao: Sessao) -> Resultado:
    """Roda UMA ação na sessão do plano. Erro de sessão/login vira passo com
    falha (interrompe o plano) em vez de exceção solta."""
    try:
        return FERRAMENTAS[acao.ferramenta].executar(acao.args, sessao)
    except ErroSessao as e:
        return Resultado(f"❌ {e}", ok=False)
