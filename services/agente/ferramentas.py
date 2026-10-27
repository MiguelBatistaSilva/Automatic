"""
services/agente/ferramentas.py — O que o Assistente sabe fazer.

Cada ferramenta tem quatro partes:
  1. o ESQUEMA que o modelo enxerga (nome, descrição, parâmetros);
  2. `preparar(args)` — valida e normaliza o que o modelo mandou e monta o
     cartão (`Acao`). Devolve `str` quando falta algo: a mensagem volta ao
     modelo, que pergunta ao técnico em vez de chutar;
  3. `executar(args, sessao)` — roda de verdade, chamando os fluxos
     (services/fluxos/flow_*_pw.py) na página da `Sessao` do plano: um login e uma
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
import datetime
import difflib
import re
import unicodedata
from typing import Callable

from services.regras.requisicao_campos import ORDEM_COLUNAS, POR_CHAVE, SEPARADOR
from services.regras.sla_engine import FILAS, FILA_PADRAO
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
    # False = roda só no computador do técnico (ex.: gerar o termo): sem
    # login nem navegador, se o plano inteiro for assim (10/10).
    assyst: bool = True


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
    # DOMÍNIO (07/10): só vai para a IA quando o pedido é desse domínio (ver
    # services/agente/roteador.py). Mesmo nome da subpasta em conhecimento/.
    # "geral" = vai sempre. Tupla = vale em mais de um (ex.: achar o chamado
    # pelo nome serve a chamados E a termos).
    dominio: "str | tuple[str, ...]" = "geral"
    # LEITURA PELO CÓDIGO antes do `preparar` (10/10): busca no Assyst o que
    # o cartão precisa e a IA não deve ver (ex.: matrícula do usuário
    # afetado, LGPD) — sem ida a mais à IA. Recebe os args e a Sessao e
    # devolve os args completados; quem chama trata falha como "não leu".
    antes: Callable[[dict, "Sessao"], dict] | None = None
    # QUANDO rodar o `antes` (21/10). Sem isto: só com o pedido completo. Com
    # isto: quando ela disser — a leitura pode ser justamente o que responde
    # a pergunta (ex.: em que fila o chamado está, na Atribuição Interna).
    precisa_ler: Callable[[dict], bool] | None = None


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
    from services.dados import kb_store
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


# Vai junto de toda dúvida sobre base (08/10): num pedido com DUAS bases
# ("a do Itom e a da Nomenclatura") a IA consultou só a primeira e INVENTOU
# nomes para a segunda ("BC - Nomenclatura de Equipamentos", que não existe).
_SO_NOMES_REAIS = (" ANTES de perguntar: se o pedido cita OUTRAS bases, chame "
                   "aplicar_base para cada uma também, e pergunte tudo de uma vez. "
                   "Cite SÓ nomes de base que vieram das ferramentas — nunca invente "
                   "exemplos.")


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
                    "Pergunte ao técnico qual delas." + _SO_NOMES_REAIS)
    parecidas = difflib.get_close_matches(nome or "", nomes, n=8, cutoff=0.3)
    parecidas += [n for n in nomes if alvo and alvo in n.lower() and n not in parecidas]
    if parecidas:
        return "", ("Base de Conhecimento não encontrada: "
                    f"'{nome}'. Parecidas: {', '.join(parecidas[:10])}. "
                    "Pergunte ao técnico qual delas." + _SO_NOMES_REAIS)
    return "", (f"Base de Conhecimento não encontrada: '{nome}'. Use "
                "listar_bases_conhecimento para ver as cadastradas." + _SO_NOMES_REAIS)


def _lista_curta(itens: list[str], limite: int = 12) -> str:
    if len(itens) <= limite:
        return ", ".join(itens)
    return ", ".join(itens[:limite]) + f" … (+{len(itens) - limite})"


def _ok_falha(ok: bool) -> str:
    return "✅" if ok else "❌"


# --------------------------------------------------------------------------- #
# Bases de Conhecimento (local)
# --------------------------------------------------------------------------- #

def _local_conhecimento(args: dict) -> str:
    """Um assunto da base de conhecimento — para o que está FORA do domínio
    do pedido (o do domínio já vem nas instruções)."""
    from services.agente import conhecimento
    return conhecimento.ler(args.get("assunto") or "")


def _desc_conhecimento() -> str:
    from services.agente import conhecimento
    return ("Lê um assunto da base de conhecimento do CATI (regras, nomes, "
            "como fazer). Use quando o pedido precisar de um assunto que não "
            "está nas instruções. Assuntos:\n" + conhecimento.indice())


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
    pedido = str(args.get("_pedido") or "")
    if not tombos:
        if args.get("_lido_do_chamado"):
            return ("A descrição do chamado não traz tombos. Pergunte ao técnico os "
                    "tombos (um filho por tombo).")
        return "Falta a lista de tombos (um filho por tombo). Pergunte ao técnico."
    if not descricao:
        if pedido:
            # Ficha (23/10): a IA monta a descrição dos filhos do Pedido, sem
            # perguntar — o técnico confere no cartão.
            return ("Chame de novo com `descricao` dos filhos montada a partir do "
                    "Pedido do chamado: curta, formal, sem local nem nomes (ex.: "
                    "'Instalação de monitor.'). Não pergunte ao técnico. Tombos: "
                    f'{", ".join(tombos)}. Pedido: "{pedido}"')
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


def _precisa_ler_desmembrar(args: dict) -> bool:
    """Sem tombos ou sem descrição: a ficha do pai tem os dois (23/10)."""
    return bool(str(args.get("chamado_pai") or "").strip()) and not (
        _lista(args.get("tombos")) and str(args.get("descricao") or "").strip())


def _antes_desmembrar(args: dict, s: Sessao) -> dict:
    from services.agente.ficha import ler_ficha

    f = ler_ficha(s.pagina, str(args.get("chamado_pai") or ""), s.log)
    if f is None:
        return args
    out = {**args, "_lido_do_chamado": True, "_pedido": f.pedido}
    if not _lista(args.get("tombos")) and f.tombos:
        out["tombos"] = f.tombos
    return out


def _kb_config(nome_base: str) -> dict:
    from services.dados import kb_store
    e = next(e for e in kb_store.carregar() if e["nome_artigo"] == nome_base)
    return {"keyword": e["keyword"], "nome_artigo": e["nome_artigo"]}


def _exec_desmembrar(a: dict, s: Sessao) -> Resultado:
    """As mesmas classes que a página de Desmembramento usa, na página da
    sessão do plano. O login delas vê a sessão ativa e segue."""
    import pandas as pd
    from services.dados import checkpoint
    from services.fluxos.flow_desmembramento_pw import FluxoCompletoPW, FluxoCriarPW
    from services.fluxos.kb_manager_pw import executar_kb_unica_pw

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
    from services.dados import checkpoint
    from services.fluxos.flow_desmembramento_pw import FluxoBCPW, _chave_checkpoint
    from services.fluxos.kb_manager_pw import executar_kb_unica_pw

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
    from services.dados import checkpoint
    from services.fluxos.flow_requisicao_pw import _chave_checkpoint, parse_entrada

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
    from services.fluxos.flow_requisicao_pw import parse_entrada

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
    from services.dados import checkpoint as cp
    from services.fluxos.flow_requisicao_pw import (
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
            if a.get("supervisor_novo"):  # plantões: confirmada e criada -> lembra
                _salvar_supervisor(a.pop("supervisor_novo"))
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
    lista = f"Cadastrados: {', '.join(opcoes)}. " if len(opcoes) <= 15 else ""
    return "", (f"{rotulo} '{valor}' não está cadastrado. {lista}"
                f"Pergunte ao técnico qual é (ou peça para "
                "cadastrar em Configurações -> Presets).")


def _opcoes() -> dict[str, list[str]]:
    from services.dados import referencia, requisicao_presets
    p = requisicao_presets.carregar()
    filas = list(dict.fromkeys(p["grupo_atribuido"] + list(FILAS)))
    # Técnicos: o banco de técnicos (nome exato do Assyst) + os dos Presets,
    # senão quem não está nos Presets "não está cadastrado" (23/10). Mesmo nome
    # com/sem acento fica o do banco.
    tecnicos = {}
    for n in referencia.tecnicos() + p["usuario_atribuido"]:
        tecnicos.setdefault(_sem_acento(n), n)
    return {"tecnicos": sorted(tecnicos.values()), "filas": filas,
            "edificios": p["edificio"], "itens": p["item"]}


def _tecnico_da_req(dito: str, opcoes: list[str], rotulo: str = "O técnico") -> tuple[str, str]:
    """(nome, erro) do técnico da Requisição: primeiro pelo banco de técnicos
    (mesma regra da atribuição: cada palavra é começo de palavra do nome),
    depois pelos Presets."""
    from services.dados import referencia

    achou = referencia.resolver_tecnico(dito or "")
    if achou.ok:
        return achou.valor, ""
    if achou.opcoes:
        return "", f"{rotulo} '{dito}' é ambíguo: {', '.join(achou.opcoes)}. Pergunte qual."
    return _resolver_nome(dito, opcoes, rotulo)


def _fila_da_req(dita: str, tecnico: str, opcoes: list[str]) -> tuple[str, str]:
    """(fila, erro). Sem fila dita: a do técnico, se ele tiver UMA só."""
    from services.dados import referencia

    dita = (dita or "").strip()
    if not dita:
        dele = referencia.filas_do_tecnico(tecnico)
        if len(dele) == 1:
            return dele[0], ""
        if dele:
            return "", f"{tecnico} atende {' e '.join(dele)}. Pergunte em qual fila."
        return "", "Falta a fila. Pergunte ao técnico."
    achou = referencia.resolver_fila(dita)
    if achou.ok:
        return achou.valor, ""
    if achou.opcoes:
        return "", f"Fila '{dita}' ambígua: {', '.join(achou.opcoes)}. Pergunte qual."
    return _resolver_nome(dita, opcoes, "A fila")


def _aviso_fila(tecnico: str, fila: str) -> str:
    """Técnico fora da fila: o Assyst pode não achá-lo no type-ahead. Só
    avisa — o banco de técnicos ainda não tem todos os pares."""
    from services.dados import referencia

    dele = referencia.filas_do_tecnico(tecnico)
    if dele and fila not in dele:
        return f"{tecnico} não consta na fila {fila} (atende {', '.join(dele)})."
    return ""


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
    tecnico, erro = _tecnico_da_req(args.get("tecnico", ""), o["tecnicos"])
    if erro:
        return erro
    fila, erro = _fila_da_req(args.get("fila", ""), tecnico, o["filas"])
    if erro:
        return erro
    if not str(args.get("edificio") or "").strip():
        return "Falta o edifício. Pergunte ao técnico."
    # Edifício e Item não travam se não estiverem nos Presets (a lista ainda é
    # curta): usa o cadastrado quando bate e, senão, segue com aviso no cartão.
    avisos = [a for a in (_aviso_fila(tecnico, fila),) if a]
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
# Plantões do fim de semana (13/10)
# --------------------------------------------------------------------------- #
# A lista que o líder sempre usa: por dia, 3 Requisições (Sede, Fórum,
# Custódia). Só mudam o dia e os técnicos — um por local (a Sede também tem
# técnico desde 13/10; a lista original a mandava sem). O código monta as linhas (a IA só passa datas e
# nomes) e cai na Requisição comum: mesmo cartão, checkpoint e Copiar lista.
# Ordem das linhas = a da lista dele: todos os dias da Sede, depois Fórum,
# depois Custódia.

# (edifício, onde na descrição, horário, fila, chave do técnico em `dias`)
_PLANTOES = (
    ("Sede Judiciária", "no TJCE", "08:00 as 18:00", "2N CATI TJ", "sede"),
    ("Fórum Clóvis Beviláqua", "no Fórum", "08:00 as 18:00", "2N CATI FCB", "forum"),
    ("Externo", "na Custódia", "08:00 as 14:00", "2N CATI FCB", "custodia"),
)
# Matrícula do usuário afetado: a do SUPERVISOR. Muda quando muda a gestão,
# por isso fica no banco (app_config), e não no código.
_CHAVE_SUPERVISOR = "plantao_supervisor"


def _supervisor() -> str:
    from services.dados import db
    r = db.consultar("SELECT valor FROM app_config WHERE chave = ?", (_CHAVE_SUPERVISOR,))
    return r[0]["valor"] if r else ""


def _salvar_supervisor(matricula: str) -> None:
    from services.dados import db
    with db.transacao() as con:
        con.execute("INSERT OR REPLACE INTO app_config VALUES (?, ?)",
                    (_CHAVE_SUPERVISOR, matricula))


def _proximo_fim_de_semana(hoje: datetime.date) -> list[datetime.date]:
    """Sábado e domingo que vêm (sábado hoje = este)."""
    sabado = hoje + datetime.timedelta(days=(5 - hoje.weekday()) % 7)
    return [sabado, sabado + datetime.timedelta(days=1)]


def _data_plantao(v: str, hoje: datetime.date) -> datetime.date:
    """'04/10' ou '04/10/2026'. Sem ano: o deste ano, ou do próximo se já passou."""
    m = re.fullmatch(r"\s*(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\s*", str(v))
    if not m:
        raise ValueError(f"Data '{v}' inválida: use dd/mm.")
    d, mes, ano = int(m[1]), int(m[2]), m[3]
    try:
        if ano:
            return datetime.date(int(ano) + (2000 if len(ano) == 2 else 0), mes, d)
        data = datetime.date(hoje.year, mes, d)
        return data if data >= hoje else datetime.date(hoje.year + 1, mes, d)
    except ValueError:
        raise ValueError(f"Data '{v}' não existe.") from None


def _prep_plantoes(args: dict) -> "Acao | str":
    hoje = datetime.date.today()
    # Matrícula dita agora só é GRAVADA ao criar de verdade (_exec_requisicoes):
    # se a IA entender errado e o líder cancelar, a salva continua valendo.
    nova = re.sub(r"\D", "", str(args.get("matricula_supervisor") or ""))
    matricula = nova or _supervisor()
    if not matricula:
        return ("Falta a matrícula do supervisor (usuário afetado dos plantões). "
                "Pergunte ao técnico; depois de informada uma vez, fica salva.")

    dias = [d for d in (args.get("dias") or []) if isinstance(d, dict)]
    padrao = _proximo_fim_de_semana(hoje)
    if not dias:
        return ("Pergunte quem fica na Sede, no Fórum e na Custódia em cada dia: "
                + " e ".join(f"{d:%d/%m} ({'sábado' if d.weekday() == 5 else 'domingo'})"
                             for d in padrao) + ".")
    sem_data = [d for d in dias if not str(d.get("data") or "").strip()]
    if sem_data and (len(sem_data) != len(dias) or len(dias) != 2):
        return "Falta a data de algum dia (dd/mm). Pergunte ao técnico."

    tecnicos = _opcoes()["tecnicos"]
    datas, nomes = [], []
    for i, d in enumerate(dias):
        try:
            data = padrao[i] if sem_data else _data_plantao(d["data"], hoje)
        except ValueError as e:
            return str(e)
        quem = {}
        for chave, rotulo in (("sede", "da Sede"), ("forum", "do Fórum"),
                              ("custodia", "da Custódia")):
            valor = str(d.get(chave) or "").strip()
            if not valor:
                return f"Falta o técnico {rotulo} em {data:%d/%m}. Pergunte ao técnico."
            valor, erro = _tecnico_da_req(valor, tecnicos, f"O técnico {rotulo}")
            if erro:
                return erro
            quem[chave] = valor
        datas.append(data)
        nomes.append(quem)
    if len(set(datas)) != len(datas):
        return "Há data repetida nos plantões. Confira com o técnico."

    reqs = [
        {"usuario_afetado": matricula, "edificio": edificio,
         "resumo": "Requisição de Serviço",
         "descricao": (f"Solicito acompanhamento técnico ao Plantão Judiciário que "
                       f"ocorrerá {onde} no dia {data:%d/%m/%Y}. Horário {horario}"),
         "item": "Apoio a Eventos e Audiências", "item_b": "IC NÃO LOCALIZADO",
         "categoria": "Apoio Técnico em Evento ou Reunião", "grupo_atribuido": fila,
         "usuario_atribuido": quem[chave]}
        for edificio, onde, horario, fila, chave in _PLANTOES
        for data, quem in zip(datas, nomes)
    ]
    base = _prep_requisicoes({"requisicoes": reqs})
    if isinstance(base, str):
        return base
    fora = list(dict.fromkeys(filter(None, (_aviso_fila(r["usuario_atribuido"], r["grupo_atribuido"])
                                            for r in reqs))))
    base.aviso = " ".join(fora + ([base.aviso] if base.aviso else []))
    semana = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")
    if nova and nova != _supervisor():
        base.args["supervisor_novo"] = nova
        base.aviso = " ".join(filter(None, [
            "Matrícula do supervisor NOVA: fica salva ao criar.", base.aviso]))
    base.titulo = "Plantões do fim de semana"
    base.linhas = [
        f"**Requisições:** {len(reqs)} (3 por dia) · **Usuário afetado:** {matricula}",
        *(f"**{semana[d.weekday()]} {d:%d/%m}:** Sede — {q['sede']} · "
          f"Fórum — {q['forum']} · Custódia — {q['custodia']}"
          for d, q in zip(datas, nomes)),
        _bloco_lista(base.copiar),
    ]
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
    from services.fluxos.flow_atendimento_pw import iniciar_atendimento
    return _exec_lote(iniciar_atendimento, "Iniciar Atendimento", False, False)(a, s)


def _exec_informacao(a, s):
    from services.fluxos.flow_informacao_pw import adicionar_informacao
    return _exec_lote(adicionar_informacao, "Adicionar Informação", True, True)(a, s)


def _exec_fornecedor(a, s):
    from services.fluxos.flow_fornecedor_pw import aguardar_info_fornecedor
    return _exec_lote(aguardar_info_fornecedor, "Aguardando Info do Fornecedor", True, True)(a, s)


def _exec_despacho(a, s):
    """Mesma pausa do fornecedor, mas com o script FORMATADO (respostas em
    vermelho, 26/10). Cartão de antes disso (sem `campos`): texto todo azul."""
    import functools
    from services.agente import despacho_operacao as dop
    from services.fluxos.flow_fornecedor_pw import aguardar_info_fornecedor
    html = dop.montar_html(**a["campos"]) if a.get("campos") else None
    funcao = functools.partial(aguardar_info_fornecedor, conteudo_html=html)
    return _exec_lote(funcao, "Aguardando Info do Fornecedor", True, True)(a, s)


def _exec_usuario(a, s):
    from services.fluxos.flow_usuario_pw import aguardar_info_usuario
    return _exec_lote(aguardar_info_usuario, "Aguardando Info do Usuário", True, True)(a, s)


# Retomadas do relógio (06/10): o par de cada pausa — flow_info_recebida_pw.
def _prep_recebida_usuario(args: dict) -> "Acao | str":
    r = _prep_lote("info_recebida_usuario", "Info Recebidas do Usuário", False)(args)
    if isinstance(r, Acao):
        nome = (args.get("nome") or "").strip()
        r.args["nome"] = nome
        quem = f"**{nome}**" if nome else "**NOME** (lido de cada chamado)"
        r.linhas.append("**Texto:** Pendência sanada após informações recebida do(a) "
                        f"senhor(a) {quem}, atendimento retomado.")
    return r


def _exec_recebida_usuario(a, s):
    import functools
    from services.fluxos.flow_info_recebida_pw import info_recebida_usuario
    funcao = functools.partial(info_recebida_usuario, nome=a.get("nome", ""))
    return _exec_lote(funcao, "Info Recebidas do Usuário", False, True)(a, s)


def _exec_recebida_fornecedor(a, s):
    from services.fluxos.flow_info_recebida_pw import info_recebida_fornecedor
    return _exec_lote(info_recebida_fornecedor, "Info Recebida do Fornecedor", True, True)(a, s)


def _prep_atribuir(args: dict) -> "Acao | str":
    """Atribuição Interna (21/10). Sem fila nem técnico = puxar para o técnico
    logado (o fluxo lê quem é e a fila dele do pop-up)."""
    from services.fluxos import flow_atribuicao_pw as fa

    chamados = _lista(args.get("chamados"))
    if not chamados:
        return "Falta a lista de chamados."
    para_mim = bool(args.get("para_mim"))
    fila, tecnico, aviso = _destino_atribuicao(args, para_mim)
    if fila is None:
        return tecnico  # a pergunta para o técnico
    if not para_mim and not fila:
        return "Falta a fila para onde o chamado vai. Pergunte (ou é para o próprio técnico?)."
    texto = (args.get("texto") or "").strip()
    motivo = (args.get("motivo") or "").strip()
    modo = args.get("modo") or (fa.LIVRE if texto else fa.PUXAR if para_mim else fa.ESCALONAR)
    if modo not in fa.MODOS:
        return f"Modo inválido: {modo}. Válidos: {', '.join(fa.MODOS)}."
    if modo == fa.ESCALONAR and not motivo:
        return "Falta o motivo do escalonamento (vai em 'Atividades realizadas'). Pergunte."
    if modo == fa.LIVRE and not texto:
        return "Falta o texto. Pergunte ao técnico."
    destino = (f"{fila or 'a fila do técnico'} / o próprio técnico" if para_mim
               else fila + (f" / {tecnico}" if tecnico else " (sem técnico)"))
    previa = {fa.ESCALONAR: f"Encaminhando para análise.\nAtividades realizadas: {motivo}",
              fa.PUXAR: "Prezado(a),\nInformo que sua solicitação encontra-se em análise. "
                        "Em breve entraremos em contato.",
              fa.CONTATO: "Contato com êxito, suporte realizando intervenção técnica.",
              fa.LIVRE: texto}[modo]
    return Acao(ferramenta="atribuir_chamado",
                args={"chamados": chamados, "fila": fila, "tecnico": tecnico,
                      "para_mim": para_mim, "modo": modo,
                      "detalhe": motivo if modo == fa.ESCALONAR else texto},
                titulo="Atribuição Interna",
                linhas=[f"**Chamados:** {len(chamados)} ({_lista_curta(chamados)})",
                        f"**Para:** {destino}",
                        f"**Texto:**\n{previa}"],
                escreve=True, pode_simular=True, aviso=aviso)


def _destino_atribuicao(args: dict, para_mim: bool) -> tuple:
    """(fila, técnico, aviso) com os nomes EXATOS do Assyst, pela referência
    (services/dados/referencia.py). Se precisar perguntar: (None, pergunta, "")."""
    from services.dados import referencia

    dita = str(args.get("fila") or "").strip()
    fila = ""
    if dita:
        achou = referencia.resolver_fila(dita)
        if achou.opcoes:
            return None, f"Fila '{dita}' ambígua: {', '.join(achou.opcoes)}. Pergunte qual.", ""
        if not achou.ok:
            return None, f"Não existe fila '{dita}' no Assyst. Pergunte o nome certo.", ""
        fila = achou.valor
    dito = "" if para_mim else str(args.get("tecnico") or "").strip()
    if not dito:
        return fila, "", ""
    achou = referencia.resolver_tecnico(dito)
    if achou.opcoes:
        return None, (f"Há mais de um técnico '{dito}': {', '.join(achou.opcoes)}. "
                      "Pergunte qual."), ""
    if not achou.ok:
        # A lista ainda não tem todas as filas: não bloqueia, o Assyst confere.
        aviso = f"'{dito}' não está na lista de técnicos: o Assyst confere o nome na hora."
        return fila, dito, aviso
    tecnico = achou.valor
    if fila:
        return fila, tecnico, ""
    dele = referencia.filas_do_tecnico(tecnico)
    if len(dele) == 1:
        return dele[0], tecnico, ""
    atual = args.get("_fila_atual") or ""
    if atual in dele:
        return atual, tecnico, ""
    if dele:
        return None, f"{tecnico} atende {' e '.join(dele)}. Pergunte em qual fila.", ""
    return None, f"Em que fila fica {tecnico}? Pergunte.", ""


def _precisa_ler_atribuir(args: dict) -> bool:
    """Técnico de várias filas e nenhuma fila dita: só aí vale ler o chamado."""
    from services.dados import referencia

    if args.get("fila") or args.get("para_mim") or not args.get("tecnico") \
            or not _lista(args.get("chamados")):
        return False
    achou = referencia.resolver_tecnico(str(args["tecnico"]))
    return achou.ok and len(referencia.filas_do_tecnico(achou.valor)) > 1


def _antes_atribuir(args: dict, s: Sessao) -> dict:
    """Lê a fila ATUAL do chamado: se o técnico estiver nela, o chamado fica
    onde está (ver _destino_atribuicao)."""
    from services.agente.ficha import ler_ficha

    chamados = _lista(args.get("chamados"))
    f = ler_ficha(s.pagina, chamados[0], s.log)
    return {**args, "_fila_atual": f.fila} if f and f.fila else args


def _exec_atribuir(a: dict, s: Sessao) -> Resultado:
    from services.fluxos import flow_atribuicao_pw as fa

    conteudo = fa.montar_texto(a["modo"], a["detalhe"])

    def funcao(page, log, numero, _texto, modo_teste):
        return fa.atribuir_interna(page, log, numero, conteudo, fila=a["fila"],
                                   tecnico=a["tecnico"], para_mim=a["para_mim"],
                                   modo_teste=modo_teste)
    return _exec_lote(funcao, "Atribuição Interna", True, True)({**a, "texto": ""}, s)


def _desc_despacho() -> str:
    """Só os NOMES dos modelos vão à IA; testes e defeito o código põe."""
    from services.agente import despacho_operacao as dop

    nomes = "; ".join(m.nome for m in dop.conhecimento.despachos()) or "(nenhum)"
    return ("DESPACHO ao Serviço de Operações (condenar/mandar equipamento para a "
            "Operação): pausa 'Aguardando Info do Fornecedor' com o script de "
            "despacho, que o SISTEMA monta. Escolha em defeito_modelo o modelo que "
            "casa com o defeito contado; não invente testes. Sem defeito dito, "
            f"chame sem defeito_modelo: o sistema diz o que perguntar. Modelos: {nomes}.")


def _prep_despacho(args: dict) -> "Acao | str":
    """Despacho ao Serviço de Operações (20/10): a mesma pausa do fornecedor,
    com o script montado pelo código (services/agente/despacho_operacao.py)."""
    from services.agente import despacho_operacao as dop

    chamados = _lista(args.get("chamado"))
    if len(chamados) != 1:
        return "Falta o chamado (um só: o script é de um equipamento)."
    tipo = dop.tipo_de(args.get("tipo") or "")
    if not tipo:
        return f"Tipo de equipamento inválido. Válidos: {', '.join(dop.TIPOS)}."
    v = {k: str(args.get(k) or "").strip()
         for k in ("localizacao", "marca", "modelo", "serie", "tombo", "obs")}
    faltam = [rot for k, rot in (("localizacao", "localização do equipamento"),
                                 ("marca", "marca"), ("modelo", "modelo"),
                                 ("serie", "nº de série")) if not v[k]]
    if dop.tem_tombo(tipo) and not v["tombo"]:
        faltam.append("tombo")
    testes = dop.itens(args.get("testes") or "")
    defeitos = dop.itens(args.get("defeito") or "")

    # Testes/defeito não ditos: saem do MODELO POR DEFEITO da equipe
    # (conhecimento/chamados/despachos.md, 26/10). A IA só escolhe o modelo;
    # se não deu para saber qual, pergunta junto com o que mais faltar.
    escolhido, pergunta = None, ""
    modelos = dop.modelos_de(tipo)
    if modelos and not (testes and defeitos):
        pelo_modelo = str(args.get("defeito_modelo") or "").strip()
        achados = dop.achar_modelo(tipo, pelo_modelo or " ".join(defeitos))
        if len(achados) == 1:
            escolhido = achados[0]
            if not pelo_modelo:
                # O "defeito" era só o problema contado ("botão direito"),
                # que serviu para achar o modelo: a conclusão vem dele.
                defeitos = []
        else:
            opcoes = achados or modelos
            pergunta = (f"Qual o defeito do {tipo.lower()}? Modelos: "
                        + "; ".join(m.nome for m in opcoes)
                        + " (ou ele dita os testes e o defeito)")
    if faltam or pergunta:
        partes = ([f"Falta(m): {', '.join(faltam)}"] if faltam else []) + \
                 ([pergunta] if pergunta else [])
        return ". ".join(partes) + ". Pergunte ao técnico, de uma vez."

    pronto = []
    if escolhido:
        testes = testes or escolhido.testes
        defeitos = defeitos or [escolhido.defeito]
        aviso = f"Testes e defeito do modelo \"{escolhido.nome}\": confira."
    else:
        padrao_testes, padrao_defeitos = dop.SCRIPTS[tipo]
        pronto = [nome for nome, dito in (("testes", testes), ("defeito", defeitos)) if not dito]
        testes, defeitos = testes or padrao_testes, defeitos or padrao_defeitos
        aviso = (f"{' e '.join(pronto).capitalize()} "
                 f"{'vieram' if len(pronto) > 1 or pronto == ['testes'] else 'veio'} "
                 f"do script genérico de {tipo} (sem modelo da equipe): confira."
                 if pronto else "")
    campos = {"tipo": tipo, "localizacao": v["localizacao"], "marca": v["marca"],
              "modelo": v["modelo"], "serie": v["serie"],
              "testes": testes, "defeitos": defeitos,
              "tombo": v["tombo"], "obs": v["obs"]}
    texto = dop.montar_texto(**campos)
    return Acao(ferramenta="despachar_operacao",
                args={"chamados": chamados, "texto": texto, "campos": campos},
                titulo="Despacho ao Serviço de Operações",
                linhas=[f"**Chamado:** {chamados[0]} · Aguardando Info do Fornecedor",
                        f"**Texto:**\n{texto}"],
                escreve=True, pode_simular=True, aviso=aviso)


# --------------------------------------------------------------------------- #
# Configurar filas (06/10) — consulta salva do monitor; não mexe em chamado
# --------------------------------------------------------------------------- #

def _prep_config_filas(args: dict) -> "Acao | str":
    from services.fluxos.flow_config_fila_pw import COLUNAS_PADRAO, PERFIL_PADRAO
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
    from services.fluxos.flow_config_fila_pw import PERFIL_PADRAO, configurar_fila, garantir_perfil
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
    from services.fluxos.flow_programar_pw import normalizar_dia, normalizar_hora

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
    from services.fluxos.flow_programar_pw import programar_atendimento
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
    from services.fluxos.flow_minhafila_pw import ler_fila
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
    from services.assyst.browser_pw import _usuario_afetado_pw
    from services.fluxos.flow_sla_pw import extrair_historico_chamado
    from services.regras.sla_engine import calcular_sla

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
    from services.fluxos.flow_resolver_pw import resolver_chamado
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
# Termo de Responsabilidade de Instalação (troca de máquina) — 10/10
# --------------------------------------------------------------------------- #
#
# Roda no computador do técnico (services/termos): não mexe no Assyst. O que
# vem do chamado (nome, matrícula e unidade do usuário afetado) é lido pelo
# CÓDIGO em `_antes_termo` e vai direto para o cartão — a IA não vê a
# matrícula. O que o técnico não souber sai em branco no documento.

_CAMPOS_EQUIP = ("marca_modelo", "tombo", "serie", "hostname")
# Repetido em "saiu" e "entrou" (sem $ref: o Gemini não aceita).
_EQUIP_ESQUEMA = {"type": "object", "properties": {
    "marca_modelo": {"type": "string", "description": "Ex.: POSITIVO C6200. Sem o tombo."},
    "tombo": {"type": "string", "description": "Patrimônio: só números, em geral 6 dígitos."},
    "serie": {"type": "string", "description": "Nº de série: letras e números (ex.: 1AM03Y878)."},
    "hostname": {"type": "string", "description":
                 "Nome da máquina na rede (ex.: FCB13CRIM). 'Coloque o nome X' = hostname."},
}}

# Marcas na grafia do patrimônio; erro de digitação ("Lennovo") cai na mais
# parecida.
_MARCAS = ("POSITIVO", "LENOVO", "DELL", "HP", "DATEN", "ITAUTEC", "ACER", "SAMSUNG", "LG")
_RE_TOMBO = re.compile(r"\b\d{5,7}\b")
# Modelo solto (C6200, M70Q) que a IA pôs no hostname. Hostname do TJ é maior
# (FCB13CRIM), então não casa.
_RE_MODELO = re.compile(r"^[A-Za-z]{1,2}\d{3,4}[A-Za-z]?$")
_RE_HOSTNAME = re.compile(r"^(?=.*\d)[A-Za-z0-9-]{6,}$")


def _equip(v) -> dict:
    v = v if isinstance(v, dict) else {}
    e = {k: re.sub(r"\s+", " ", str(v.get(k) or "")).strip() for k in _CAMPOS_EQUIP}
    if not e["marca_modelo"] and _RE_MODELO.match(e["hostname"]):
        e["marca_modelo"], e["hostname"] = e["hostname"], ""
    # Tombo grudado no modelo ("Lenovo 333232"): separa.
    numeros = _RE_TOMBO.findall(e["marca_modelo"])
    if numeros and (not e["tombo"] or e["tombo"] in numeros):
        e["tombo"] = e["tombo"] or numeros[0]
        e["marca_modelo"] = " ".join(_RE_TOMBO.sub(" ", e["marca_modelo"]).split())
    palavras = e["marca_modelo"].split(" ", 1)
    marca = difflib.get_close_matches(palavras[0].upper(), _MARCAS, n=1, cutoff=0.75)
    if marca:
        e["marca_modelo"] = " ".join([marca[0], *palavras[1:]])
    e["hostname"] = e["hostname"].upper()
    return e


def _arrumar_trocas(trocas: list[dict], hostname: str) -> None:
    """Na troca a máquina nova herda o nome da antiga: hostname dito só de um
    lado (ou solto no pedido) vale para os dois."""
    solto = hostname if len(trocas) == 1 else ""
    for t in trocas:
        um = t["saiu"]["hostname"] or t["entrou"]["hostname"] or solto
        t["saiu"]["hostname"] = t["saiu"]["hostname"] or um
        t["entrou"]["hostname"] = t["entrou"]["hostname"] or um


def _hostname_fora_do_nome(args: dict) -> dict:
    """"Coloque o nome FCB13CRIM" virava o NOME DO USUÁRIO no termo (21/10):
    `nome` com cara de hostname sai do nome e vai para `_hostname`."""
    nome = str(args.get("nome") or "").strip()
    if " " in nome or not _RE_HOSTNAME.match(nome):
        return args
    return {**args, "nome": "", "_hostname": nome.upper()}


def _antes_termo(args: dict, s: Sessao) -> dict:
    """Lê nome, matrícula e unidade do usuário afetado do chamado. O que o
    técnico disse na conversa vale mais que o lido."""
    from services.assyst.assyst_common import _so_o_nome
    from services.agente.ficha import ler_ficha

    args = _hostname_fora_do_nome(args)
    f = ler_ficha(s.pagina, str(args.get("chamado") or ""), s.log)
    if f is None:
        return args
    return _completar(args, {"matricula": f.afetado_matricula, "nome": f.afetado_nome,
                             "unidade": _so_o_nome(f.secao) if f.secao else ""})


def _completar(args: dict, lido: dict) -> dict:
    """O lido do chamado preenche só o que o técnico NÃO disse na conversa."""
    return {**args, **{k: v for k, v in lido.items()
                       if v and not str(args.get(k) or "").strip()},
            "_lido_do_chamado": True}


def _prep_termo(args: dict) -> "Acao | str":
    if not isinstance(args.get("backup"), bool):
        return "Falta saber se foi COM ou SEM backup. Pergunte."
    trocas = [{"saiu": _equip(m.get("saiu")), "entrou": _equip(m.get("entrou"))}
              for m in (args.get("maquinas") or []) if isinstance(m, dict)]
    trocas = [t for t in trocas if any(t["saiu"].values()) or any(t["entrou"].values())]
    if not trocas:
        return ("Faltam as máquinas trocadas. Pergunte, de uma vez, para cada troca: "
                "a que saiu e a que entrou (marca/modelo, tombo, nº de série, hostname). "
                "O que o técnico não souber fica em branco.")
    args = _hostname_fora_do_nome(args)
    _arrumar_trocas(trocas, args.get("_hostname", ""))
    a = {
        "chamado": str(args.get("chamado") or "").strip().upper(),
        "backup": args["backup"],
        "maquinas": trocas,
        **{k: str(args.get(k) or "").strip() for k in ("nome", "matricula", "unidade",
                                                        "observacoes")},
        "onedrive": args.get("onedrive") if isinstance(args.get("onedrive"), bool) else None,
    }

    def ou_branco(v: str) -> str:
        return v or "*(em branco)*"

    def maquina(e: dict) -> str:
        partes = [f"{rotulo} {e[k]}" for k, rotulo in
                  (("tombo", "tombo"), ("serie", "série"), ("hostname", "hostname")) if e[k]]
        nome = e["marca_modelo"] or "?"
        return f"{nome} ({', '.join(partes)})" if partes else nome

    linhas = [
        f"**Chamado:** {ou_branco(a['chamado'])} · **Data:** "
        f"{datetime.date.today():%d/%m/%Y}",
        f"**Tipo:** {'Com' if a['backup'] else 'Sem'} backup e restore",
        f"**Usuário:** {ou_branco(a['nome'])} · **Matrícula:** {ou_branco(a['matricula'])}",
        f"**Unidade:** {ou_branco(a['unidade'])}",
    ]
    if a["backup"]:
        linhas.append("**Backup pelo OneDrive oferecido?** " + (
            "não marcado" if a["onedrive"] is None else ("Sim" if a["onedrive"] else "Não")))
    for n, t in enumerate(trocas, 1):
        rotulo = f"Máquina {n}" if len(trocas) > 1 else "Máquina"
        linhas.append(f"**{rotulo}:** {maquina(t['saiu'])} → {maquina(t['entrou'])}")
    if a["observacoes"]:
        linhas.append(f"**Observações:** {a['observacoes']}")
    aviso = ""
    if a["chamado"] and not args.get("_lido_do_chamado"):
        aviso = "Não consegui ler o usuário afetado do chamado: confira nome, matrícula e unidade."
    return Acao(ferramenta="gerar_termo", args=a,
                titulo="Termo de Responsabilidade de Instalação", linhas=linhas,
                escreve=True,
                # "Simular" gera o termo igual (é local): o botão só existe
                # para não sumir de um plano junto com passos do Assyst.
                pode_simular=True, assyst=False, aviso=aviso)


def _termo_de(a: dict):
    from services import termos
    return termos.Termo(
        backup=a["backup"], unidade=a["unidade"], chamado=a["chamado"],
        data=datetime.date.today(),
        trocas=[termos.Troca(termos.Equipamento(**t["saiu"]),
                             termos.Equipamento(**t["entrou"])) for t in a["maquinas"]],
        recebedor=termos.Pessoa(a["nome"], a["matricula"]),
        onedrive=a["onedrive"], observacoes=a["observacoes"])


def _exec_termo(a: dict, s: Sessao) -> Resultado:
    from services import termos
    s.log("Gerando o termo...", "status")
    try:
        odt, pdf, erro_pdf = termos.gerar(_termo_de(a))
    except Exception as e:
        return Resultado(f"❌ Não consegui gerar o termo: {e}", ok=False)
    ref = f" do {a['chamado']}" if a["chamado"] else ""
    if pdf is None:
        return Resultado(f"⚠️ **Termo{ref} gerado só em ODT** — o PDF falhou ({erro_pdf}).",
                         arquivos=[str(odt)])
    return Resultado(f"✅ **Termo{ref} gerado.**", arquivos=[str(pdf), str(odt)])


# --------------------------------------------------------------------------- #
# Termo de Tarefa de Demanda (eventos) — 10/10
# --------------------------------------------------------------------------- #
#
# Quase tudo vem do chamado, lido pelo CÓDIGO (`_antes_demanda`): solicitante,
# Início/Fim agendado, nome do técnico e a DESCRIÇÃO — de onde saem o local e
# a descrição do evento (services/termos/demanda.py). A descrição NUNCA vai
# para a IA: no fim dela vem colado CPF, telefone e nascimento do solicitante.
# Do técnico: validador, horário real do evento e OBS.

def _hora(v) -> str:
    """'10h' / '10:00' / '9h30' / '9' -> 'hh:mm'; o resto passa como veio."""
    t = str(v or "").strip()
    m = re.fullmatch(r"(\d{1,2})\s*(?:[:h]\s*(\d{2})?)?\s*(?:h|hs|horas)?", t, re.I)
    if not m or int(m[1]) > 23:
        return t
    return f"{int(m[1]):02d}:{m[2] or '00'}"


def _antes_demanda(args: dict, s: Sessao) -> dict:
    """Tudo pela FICHA do chamado (services/agente/ficha.py, 23/10). O local segue a
    regra única: técnico/IA > 'Local:' na descrição > (a IA lê do Pedido) >
    Edifício + Sala do chamado — os dois últimos resolvidos no _prep_demanda."""
    from services.agente.ficha import ler_ficha
    from services.termos.demanda import nome_proprio

    f = ler_ficha(s.pagina, str(args.get("chamado") or ""), s.log)
    if f is None:
        return args
    dito = str(args.get("local") or "").strip()
    out = _completar(args, {
        "solicitante": nome_proprio(f.afetado_nome),
        "data": f.inicio_data,
        "inicio_previsto": f.inicio_hora,
        "fim_previsto": f.fim_hora,
        "local": f.local_descrito,
        "descricao": f.evento,
        "tecnico_nome": f.tecnico_logado,
        "tecnico_matricula": s.matricula,
    })
    out["_origem_local"] = "" if dito else ("descrição" if f.local_descrito else "")
    out["_local_chamado"] = f.local_do_chamado
    out["_pedido"] = f.pedido
    return out


_CAMPOS_DEMANDA = ("chamado", "solicitante", "data", "inicio_previsto", "fim_previsto",
                   "local", "descricao", "validador_nome", "validador_matricula",
                   "inicio", "fim", "obs", "tecnico_nome", "tecnico_matricula")


def _prep_demanda(args: dict) -> "Acao | str":
    a = {k: str(args.get(k) or "").strip() for k in _CAMPOS_DEMANDA}
    a["chamado"] = a["chamado"].upper()
    if not a["chamado"]:
        return "Falta o número do chamado do evento (os dados do evento vêm dele)."
    if not a["validador_nome"] and args.get("validador_a_mao") is not True:
        # Sem isto o modelo gerava direto, com o validador em branco (teste
        # de 10/10): só o técnico sabe quem validou — tem que perguntar.
        faltam = ["quem foi o VALIDADOR (nome e matrícula)"]
        if not (a["inicio"] or a["fim"]):
            faltam.append("o horário em que ele COMEÇOU e TERMINOU de fato")
        if not a["obs"]:
            faltam.append("a OBS (o que ele fez no evento)")
        pedido = str(args.get("_pedido") or "")
        local = ("" if a["local"] or not pedido else
                 " Na próxima chamada, passe também `local` = onde é o evento, se o "
                 f'Pedido do chamado disser (não pergunte isso ao técnico): "{pedido}"')
        return ("Antes de gerar, pergunte ao técnico numa mensagem só: "
                + "; ".join(faltam) + ". Se ele disser que o validador vai ser "
                "preenchido à mão, chame de novo com validador_a_mao=true." + local)
    for k in ("inicio_previsto", "fim_previsto", "inicio", "fim"):
        a[k] = _hora(a[k])
    # Regra única do local (23/10): técnico/IA > descrição > Edifício + Sala.
    nota_local = "da descrição" if args.get("_origem_local") == "descrição" else ""
    if not a["local"] and args.get("_local_chamado"):
        a["local"], nota_local = args["_local_chamado"], "do Edifício/Sala do chamado"

    def ou_branco(v: str, motivo: str = "") -> str:
        return v or f"*(em branco{' — ' + motivo if motivo else ''})*"

    previsto = f"{a['inicio_previsto'] or '?'} às {a['fim_previsto'] or '?'}"
    execucao = (f"{a['inicio'] or a['inicio_previsto'] or '?'} às "
                f"{a['fim'] or a['fim_previsto'] or '?'}")
    if not (a["inicio"] or a["fim"]):
        execucao += " *(o agendado — o técnico não informou)*"
    tecnico = a["tecnico_nome"] + (f" — mat. {a['tecnico_matricula']}"
                                   if a["tecnico_matricula"] else "")
    linhas = [
        f"**Chamado:** {a['chamado']} · **Data do serviço:** {ou_branco(a['data'])}",
        f"**Solicitante/Requisitante:** {ou_branco(a['solicitante'])}",
        f"**Local:** {ou_branco(a['local'], 'não achei no chamado')}"
        + (f" *({nota_local})*" if a["local"] and nota_local else ""),
        f"**Horário previsto:** {previsto}",
        f"**Descrição do evento:** {ou_branco(a['descricao'], 'não achei na descrição')}",
        f"**Validador:** {ou_branco(a['validador_nome'])} · "
        f"**Matrícula:** {ou_branco(a['validador_matricula'])}",
        f"**Horário de execução:** {execucao}",
        f"**Técnico:** {ou_branco(tecnico)}",
        f"**OBS:** {ou_branco(a['obs'])}",
    ]
    aviso = "" if args.get("_lido_do_chamado") else (
        "Não consegui ler o chamado no Assyst: os dados do evento vão em branco.")
    return Acao(ferramenta="gerar_termo_demanda", args=a,
                titulo="Termo de Tarefa de Demanda", linhas=linhas, escreve=True,
                pode_simular=True, assyst=False, aviso=aviso)


def _exec_demanda(a: dict, s: Sessao) -> Resultado:
    from services import termos
    from services.termos.demanda import TermoDemanda
    s.log("Gerando o termo de demanda...", "status")
    try:
        data = datetime.datetime.strptime(a["data"], "%d/%m/%Y").date() if a["data"] else None
    except ValueError:
        data = None
    t = TermoDemanda(
        chamado=a["chamado"], solicitante=a["solicitante"], local=a["local"], data=data,
        inicio_previsto=a["inicio_previsto"], fim_previsto=a["fim_previsto"],
        descricao=a["descricao"],
        validador=termos.Pessoa(a["validador_nome"], a["validador_matricula"]),
        inicio=a["inicio"], fim=a["fim"],
        tecnico=termos.Pessoa(a["tecnico_nome"], a["tecnico_matricula"]), obs=a["obs"])
    try:
        odt, pdf, erro_pdf = termos.gerar_demanda(t)
    except Exception as e:
        return Resultado(f"❌ Não consegui gerar o termo de demanda: {e}", ok=False)
    if pdf is None:
        return Resultado(f"⚠️ **Termo de demanda do {a['chamado']} gerado só em ODT** — "
                         f"o PDF falhou ({erro_pdf}).", arquivos=[str(odt)])
    return Resultado(f"✅ **Termo de demanda do {a['chamado']} gerado.**",
                     arquivos=[str(pdf), str(odt)])


# --------------------------------------------------------------------------- #
# Investigação — leituras cujo resultado volta para a IA (2026-10-01)
# --------------------------------------------------------------------------- #

def _inv_buscar_chamado(args: dict, s: Sessao) -> str:
    """Acha o chamado pelo NOME do usuário (e setor) na fila do técnico — os
    técnicos lembram de "o chamado da Carla", não do número. A comparação é
    feita aqui no código; para a IA só vão os chamados que BATEM com o nome
    que o próprio técnico citou, nunca a fila inteira."""
    from services.fluxos.flow_minhafila_pw import ler_fila

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
    # "Todos os chamados do Fulano" (22/10): lote, sem perguntar — o cartão
    # mostra a lista para o técnico confirmar.
    if args.get("todos"):
        nomes = {_sem_acento(c.get("afetado", "")) for c in batem}
        aviso = ("" if len(nomes) == 1 else
                 " ATENÇÃO: são pessoas diferentes com esse nome; pergunte se são todas.")
        return (f"{len(batem)} chamados de '{args.get('nome')}' (use TODOS no próximo "
                f"passo): " + "; ".join(linhas) + "." + aviso)
    return (f"{len(batem)} chamados batem com '{args.get('nome')}': " + "; ".join(linhas)
            + ". Pergunte ao técnico qual (mostre nome e setor).")


def _inv_verificar_sla(args: dict, s: Sessao) -> str:
    """SLA para a IA DECIDIR: só número, fila e tempo — nada do usuário."""
    from services.fluxos.flow_sla_pw import extrair_historico_chamado
    from services.regras.sla_engine import calcular_sla

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
# Triagem do chamado (22/10) — o Assistente olhando como técnico
# --------------------------------------------------------------------------- #
#
# Regras em services/agente/triagem.py. A DESCRIÇÃO é lida pelo código; a IA recebe
# seção, edifício, Item B, os tombos e o PEDIDO sem o bloco de dados pessoais
# (triagem.pedido_seguro) — para propor o desmembramento sem perguntar.

_MAX_TRIAGEM = 15   # ~5 s por chamado: a conversa não pode ficar presa


def _inv_analisar_chamado(args: dict, s: Sessao) -> str:
    from services.agente.ficha import ler_ficha
    from services.agente.triagem import triar_ficha

    chamados = _lista(args.get("chamados"))
    page, saida = s.pagina(), []
    if args.get("minha_fila"):
        # "Analisa minha fila" (22/10): lê a fila AQUI — para a IA vão só os
        # números (os nomes dos usuários ficam no código).
        from services.fluxos.flow_minhafila_pw import ler_fila
        fila = ler_fila(page, s.log)
        if fila is None:
            return "Não consegui ler a fila do técnico (a tela não carregou)."
        if not fila:
            return "A fila do técnico está VAZIA: não há chamado para analisar."
        chamados = [c["referencia"] for c in fila if c.get("referencia")]
        saida.append(f"Fila do técnico: {len(chamados)} chamado(s)"
                     + (f"; analisados os {_MAX_TRIAGEM} primeiros" if len(chamados) > _MAX_TRIAGEM else "")
                     + ".")
        chamados = chamados[:_MAX_TRIAGEM]
    if not chamados:
        return "Falta o número do chamado (ou minha_fila=true)."
    for numero in (c.strip().upper() for c in chamados):
        # Relê (recente=False): o técnico pode ter acabado de corrigir algo.
        f = ler_ficha(lambda: page, numero, s.log, recente=False)
        if f is None:
            saida.append(f"{numero}: não consegui abrir o chamado")
            continue
        saida.append(triar_ficha(f).resumo())
    return "\n".join(saida)


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
        "consultar_conhecimento",
        _desc_conhecimento,  # montada na hora: o índice dos assuntos
        {"type": "object", "properties": {
            "assunto": {"type": "string", "description": "Chave do índice (ex.: chamados/sla)."},
        }, "required": ["assunto"]},
        preparar=lambda a: "", local=_local_conhecimento,
        dominio="geral",
    ),
    Ferramenta(
        "buscar_chamado_por_usuario",
        "INVESTIGAÇÃO: acha o chamado na fila do técnico pelo nome do usuário afetado.",
        {"type": "object", "properties": {
            "nome": {"type": "string"},
            "setor": {"type": "string"},
            "todos": {"type": "boolean", "description":
                      "true se o técnico disse TODOS os chamados dessa pessoa."},
        }, "required": ["nome"]},
        preparar=lambda a: "", investiga=_inv_buscar_chamado,
        dominio=("chamados", "termos"),
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
        dominio="chamados",
    ),
    Ferramenta(
        "verificar_sla",
        "INVESTIGAÇÃO: diz se o chamado está NO PRAZO ou ESTOURADO e quanto resta.",
        {"type": "object", "properties": {
            "chamados": _CHAMADOS,
            "fila": _FILA,
        }, "required": ["chamados"]},
        preparar=lambda a: "", investiga=_inv_verificar_sla,
        dominio="chamados",
    ),
    Ferramenta(
        "analisar_chamado",
        "INVESTIGAÇÃO (triagem): confere Edifício e Item B do chamado e diz o "
        "que corrigir (só leitura).",
        {"type": "object", "properties": {
            "chamados": _CHAMADOS,
            "minha_fila": {"type": "boolean", "description":
                           "true = analisar os chamados da fila do técnico."},
        }},
        preparar=lambda a: "", investiga=_inv_analisar_chamado,
        dominio="chamados",
    ),
    Ferramenta(
        "listar_bases_conhecimento",
        "Lista as Bases de Conhecimento cadastradas (filtro: palavras do nome).",
        {"type": "object", "properties": {"filtro": {"type": "string"}}},
        preparar=lambda a: "", local=_local_bases,
        dominio="chamados",
    ),
    Ferramenta(
        "desmembrar",
        "Cria um chamado filho por tombo a partir do pai; com 'base', aplica a "
        "base em cada filho.",
        {"type": "object", "properties": {
            "chamado_pai": {"type": "string"},
            "tombos": {"type": "array", "items": {"type": "string"}, "description":
                       "Os que o técnico disse; sem eles, o sistema lê do chamado."},
            "descricao": {"type": "string", "description":
                          "Dos filhos. {{tombo}} onde entra o tombo (sem ele, vai no fim)."},
            "base": {"type": "string", "description": "Nome ou palavras da base."},
        }, "required": ["chamado_pai"]},
        preparar=_prep_desmembrar, executar=_exec_desmembrar,
        # Tombos e descrição que faltarem vêm da ficha do pai (23/10).
        antes=_antes_desmembrar, precisa_ler=_precisa_ler_desmembrar,
        dominio="chamados",
    ),
    Ferramenta(
        "aplicar_base",
        "Aplica uma Base de Conhecimento em chamados que já existem. Uma chamada "
        "por base.",
        {"type": "object", "properties": {
            "chamados": _CHAMADOS,
            "base": {"type": "string", "description":
                     "As palavras que o técnico disse (ex.: 'memória'); o sistema acha "
                     "a base ou devolve as opções. Não peça o nome completo antes."},
        }, "required": ["chamados", "base"]},
        preparar=_prep_aplicar_base, executar=_exec_aplicar_base,
        dominio="chamados",
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
        dominio="requisicao",
    ),
    Ferramenta(
        "criar_requisicoes_por_tombo",
        _desc_por_tombo,  # montada na hora: lê tipos e nomes do banco
        {"type": "object", "properties": {
            "matricula": {"type": "string", "description": "Do usuário afetado."},
            "edificio": {"type": "string"},
            "fila": {"type": "string", "description":
                     "Grupo atribuído. Omita se o técnico não disse: o sistema usa a do técnico."},
            "tecnico": {"type": "string", "description": "Técnico atribuído (nome ou parte)."},
            "tombos": {"type": "array", "items": {"type": "string"},
                       "description": "Como o técnico escreveu."},
            "tipo": {"type": "string", "description": "Tipo de solicitação da base que bate."},
            "item": {"type": "string", "description": "Só se nenhum tipo bater."},
            "categoria": {"type": "string"},
            "resumo": {"type": "string"},
            "descricao": {"type": "string", "description":
                          "Só se diferente da do tipo. {tombo} onde entra o tombo."},
        }, "required": ["matricula", "edificio", "tecnico"]},
        preparar=_prep_por_tombo, executar=_exec_requisicoes,
        dominio="requisicao",
    ),
    Ferramenta(
        "criar_plantoes",
        "PLANTÃO JUDICIÁRIO: abre as Requisições dos plantões (3 por dia: Sede, "
        "Fórum e Custódia). O sistema monta tudo; só passe dias e técnicos.",
        {"type": "object", "properties": {
            "dias": {"type": "array", "items": {"type": "object", "properties": {
                "data": {"type": "string", "description":
                         "dd/mm. Vazio = próximo sábado/domingo (só com 2 dias)."},
                "sede": {"type": "string", "description": "Técnico da Sede."},
                "forum": {"type": "string", "description": "Técnico do Fórum."},
                "custodia": {"type": "string", "description": "Técnico da Custódia."},
            }}},
            "matricula_supervisor": {"type": "string", "description":
                                     "Só se o técnico informar ou trocar."},
        }},
        preparar=_prep_plantoes, executar=_exec_requisicoes,
        dominio="requisicao",
    ),
    Ferramenta(
        "iniciar_atendimento",
        "Inicia o atendimento agora (ação 'Iniciar Atendimento').",
        {"type": "object", "properties": {"chamados": _CHAMADOS}, "required": ["chamados"]},
        preparar=_prep_lote("iniciar_atendimento", "Iniciar Atendimento", False),
        executar=_exec_atendimento,
        dominio="chamados",
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
        dominio="chamados",
    ),
    Ferramenta(
        "adicionar_informacao",
        "Registra um texto nos chamados (ação 'Adicionar Informação').",
        {"type": "object", "properties": {"chamados": _CHAMADOS, "texto": {"type": "string"}},
         "required": ["chamados", "texto"]},
        preparar=_prep_lote("adicionar_informacao", "Adicionar Informação", True),
        executar=_exec_informacao,
        dominio="chamados",
    ),
    Ferramenta(
        "aguardar_fornecedor",
        "PAUSA: 'Aguardando Info do Fornecedor', com um texto.",
        {"type": "object", "properties": {"chamados": _CHAMADOS, "texto": {"type": "string"}},
         "required": ["chamados", "texto"]},
        preparar=_prep_lote("aguardar_fornecedor", "Aguardando Info do Fornecedor", True),
        executar=_exec_fornecedor,
        dominio="chamados",
    ),
    Ferramenta(
        "atribuir_chamado",
        "ATRIBUIÇÃO INTERNA: passa o chamado para uma fila (com ou sem técnico) "
        "ou o técnico puxa para si (para_mim). Não mexe no SLA.",
        {"type": "object", "properties": {
            "chamados": _CHAMADOS,
            "para_mim": {"type": "boolean", "description":
                         "true = o técnico vai resolver ele mesmo (puxar/pegar para si)."},
            "fila": {"type": "string", "description":
                     "Departamento de destino (ex.: FCB, TJ, Remoto, Polo Iguatu)."},
            "tecnico": {"type": "string", "description": "Nome do técnico de destino, se dito."},
            "modo": {"type": "string", "enum": ["escalonar", "puxar", "contato", "livre"],
                     "description": "Texto padrão; ver chamados/atribuicao."},
            "motivo": {"type": "string", "description":
                       "escalonar: por que o técnico não resolveu (o que já fez)."},
            "texto": {"type": "string", "description": "livre: o texto ditado pelo técnico."},
        }, "required": ["chamados"]},
        preparar=_prep_atribuir, executar=_exec_atribuir, antes=_antes_atribuir,
        precisa_ler=_precisa_ler_atribuir,
        dominio="chamados",
    ),
    Ferramenta(
        "despachar_operacao",
        _desc_despacho,  # montada na hora: os nomes dos modelos de despacho
        {"type": "object", "properties": {
            "chamado": {"type": "string"},
            "tipo": {"type": "string", "description":
                     "Computador, Notebook, Monitor, Impressora, Teclado, Mouse, "
                     "Webcam ou Caixa de som."},
            "localizacao": {"type": "string", "description": "Dita pelo técnico."},
            "marca": {"type": "string"},
            "modelo": {"type": "string"},
            "serie": {"type": "string"},
            "tombo": {"type": "string", "description":
                      "Computador/Notebook/Monitor/Impressora. Teclado, mouse, "
                      "webcam e caixa de som não têm."},
            "obs": {"type": "string"},
            "defeito_modelo": {"type": "string", "description":
                               "Nome do modelo de despacho (lista na descrição) que "
                               "casa com o defeito que o técnico contou."},
            "testes": {"type": "string", "description":
                       "Um por linha. Só se o técnico DITAR os testes."},
            "defeito": {"type": "string", "description":
                        "Só se o técnico DITAR o texto do defeito; se ele só contou "
                        "o problema, use defeito_modelo."},
        }, "required": ["chamado", "tipo"]},
        preparar=_prep_despacho, executar=_exec_despacho,
        dominio="chamados",
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
        dominio="chamados",
    ),
    Ferramenta(
        "info_recebida_usuario",
        "RETOMADA: 'Info Recebidas do Usuário *' (texto fixo, montado pelo sistema).",
        {"type": "object", "properties": {
            "chamados": _CHAMADOS,
            "nome": {"type": "string", "description":
                     "Só se o técnico disser OUTRO nome para o texto (quem passou a "
                     "informação). Sem isso, vai o usuário do chamado."},
        }, "required": ["chamados"]},
        preparar=_prep_recebida_usuario,
        executar=_exec_recebida_usuario,
        dominio="chamados",
    ),
    Ferramenta(
        "info_recebida_fornecedor",
        "RETOMADA: 'Info Recebida do Fornecedor', com um texto.",
        {"type": "object", "properties": {"chamados": _CHAMADOS, "texto": {"type": "string"}},
         "required": ["chamados", "texto"]},
        preparar=_prep_lote("info_recebida_fornecedor", "Info Recebida do Fornecedor", True),
        executar=_exec_recebida_fornecedor,
        dominio="chamados",
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
        dominio="filas",
    ),
    Ferramenta(
        "consultar_minha_fila",
        "Lista os chamados da fila do técnico (só leitura).",
        {"type": "object", "properties": {}},
        preparar=_prep_fila, executar=_exec_fila,
        dominio="chamados",
    ),
    Ferramenta(
        "analisar_sla",
        "Mostra ao técnico o SLA (gasto/restante) dos chamados (só leitura).",
        {"type": "object", "properties": {
            "chamados": _CHAMADOS,
            "fila": _FILA,
        }, "required": ["chamados"]},
        preparar=_prep_sla, executar=_exec_sla,
        dominio="chamados",
    ),
    Ferramenta(
        "gerar_termo",
        "TROCA DE MÁQUINA: gera o Termo de Responsabilidade de Instalação "
        "(com/sem backup) em PDF. Não é o termo de evento (gerar_termo_demanda). "
        "Nome, matrícula e unidade o sistema lê do chamado.",
        {"type": "object", "properties": {
            "chamado": {"type": "string"},
            "backup": {"type": "boolean", "description": "true = COM backup e restore."},
            "maquinas": {"type": "array", "items": {"type": "object", "properties": {
                "saiu": _EQUIP_ESQUEMA,
                "entrou": _EQUIP_ESQUEMA,
            }}},
            "nome": {"type": "string", "description":
                     "Nome do USUÁRIO (pessoa), só se o técnico disser. "
                     "Nome da máquina vai em maquinas[].hostname."},
            "matricula": {"type": "string", "description": "Só se o técnico disser."},
            "unidade": {"type": "string", "description": "Só se o técnico disser."},
            "onedrive": {"type": "boolean", "description": "Com backup: oferecido pelo OneDrive?"},
            "observacoes": {"type": "string"},
        }, "required": ["backup", "maquinas"]},
        preparar=_prep_termo, executar=_exec_termo, antes=_antes_termo,
        dominio="termos",
    ),
    Ferramenta(
        "gerar_termo_demanda",
        "EVENTO / TAREFA DE DEMANDA: gera a comprovação de prestação de serviço "
        "(validador assina). Solicitante, local, horário previsto e descrição do "
        "evento o sistema lê do chamado.",
        {"type": "object", "properties": {
            "chamado": {"type": "string"},
            "validador_nome": {"type": "string", "description": "Quem valida/assina no evento."},
            "validador_matricula": {"type": "string"},
            "inicio": {"type": "string", "description": "hh:mm em que o técnico começou de fato."},
            "fim": {"type": "string", "description": "hh:mm em que terminou de fato."},
            "obs": {"type": "string", "description": "O que o técnico fez, nas palavras dele."},
            "local": {"type": "string", "description":
                      "Onde é o evento: o que o técnico disse ou o que o Pedido do chamado diz."},
            "descricao": {"type": "string", "description": "Só se o técnico corrigir."},
            "validador_a_mao": {"type": "boolean", "description":
                                "true só se o técnico disser que o validador fica em branco."},
        }, "required": ["chamado"]},
        preparar=_prep_demanda, executar=_exec_demanda, antes=_antes_demanda,
        # Lê já na 1ª chamada (23/10): a pergunta do validador leva o Pedido,
        # para a IA tirar dele o local. A ficha fica guardada para a 2ª.
        precisa_ler=lambda a: bool(str(a.get("chamado") or "").strip()),
        dominio="termos",
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


def esquemas(dominios: "set[str] | None" = None) -> list[dict]:
    """As ferramentas para a IA: as dos `dominios` + as "geral".
    None = todas (o roteador não reconheceu o pedido)."""
    return [
        {"type": "function", "function": {
            "name": f.nome,
            "description": f.descricao() if callable(f.descricao) else f.descricao,
            "parameters": _aceita_null(_com_ultima_acao(f, f.parametros))}}
        for f in FERRAMENTAS.values()
        if dominios is None or f.dominio == "geral" or _dominios_de(f) & dominios
    ]


def _dominios_de(f: Ferramenta) -> set[str]:
    return {f.dominio} if isinstance(f.dominio, str) else set(f.dominio)


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
        elif f == "atribuir_chamado":
            partes.append(f"pegar o {ch(a)} para você" if a.args["para_mim"] else
                          f"atribuir o {ch(a)} a {a.args['fila']}"
                          + (f" / {a.args['tecnico']}" if a.args["tecnico"] else ""))
        elif f == "despachar_operacao":
            partes.append(f"despachar o {ch(a)} ao Serviço de Operações")
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
        elif f == "gerar_termo_demanda":
            partes.append(f"gerar o termo de demanda do {a.args['chamado']}")
        elif f == "gerar_termo":
            ref = f" do {a.args['chamado']}" if a.args.get("chamado") else ""
            partes.append(f"gerar o termo de responsabilidade{ref}")
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
