"""
services/agente/ferramentas.py — O que o Assistente sabe fazer.

Cada ferramenta tem quatro partes:
  1. o ESQUEMA que o modelo enxerga (nome, descrição, parâmetros);
  2. `preparar(args)` — valida e normaliza o que o modelo mandou e monta o
     cartão (`Acao`). Devolve `str` quando falta algo: a mensagem volta ao
     modelo, que pergunta ao técnico em vez de chutar;
  3. `executar(...)` — roda de verdade, chamando os serviços do bot
     (bot/services/*). NENHUM arquivo de fluxo foi alterado para isto;
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
from typing import Callable

from services.requisicao_campos import ORDEM_COLUNAS, POR_CHAVE, SEPARADOR
from services.sla_engine import FILAS, FILA_PADRAO


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


@dataclasses.dataclass
class Ferramenta:
    nome: str
    descricao: str
    parametros: dict
    preparar: Callable[[dict], "Acao | str"]
    executar: Callable[..., str] | None = None
    # Ferramenta LOCAL (sem navegador): roda na hora e o resultado volta ao
    # modelo — só para dados do próprio app, nunca do Assyst.
    local: Callable[[dict], str] | None = None


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


def _resolver_base(nome: str) -> tuple[str, str]:
    """(nome_exato, erro). Aceita diferença de maiúsculas; nunca adivinha além
    disso — base errada aplicada num chamado não tem desfazer."""
    nomes = _nomes_bases()
    alvo = (nome or "").strip().lower()
    for n in nomes:
        if n.lower() == alvo:
            return n, ""
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
    filtro = (args.get("filtro") or "").strip().lower()
    if filtro:
        nomes = [n for n in nomes if filtro in n.lower()]
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


def _exec_desmembrar(a: dict, matricula, senha, log, modo_teste=False,
                     iniciar_do_zero=False) -> str:
    from bot.services import desmembramento_service as ds

    csv_texto = "tombo\n" + "\n".join(a["tombos"])
    r = ds.criar_filhos(
        a["chamado_pai"], csv_texto, a["descricao"], matricula, senha,
        kb_nome=a["base"] or None, log=log, iniciar_do_zero=iniciar_do_zero,
        origem="ui",
    )
    if not r.get("ok"):
        return f"❌ Não rodou: {r.get('erro', 'erro desconhecido')}"
    linhas = [f"**Desmembramento de {a['chamado_pai']}** — {r['concluidos']} de "
              f"{r['total']} concluído(s)."]
    for d, tombo in zip(r["detalhe"], a["tombos"]):
        feito = d["status"] == "concluido"
        filho = d["filho"] or "—"
        extra = "" if feito else f" ({d['status']})"
        linhas.append(f"- {_ok_falha(feito)} tombo {tombo} → **{filho}**{extra}")
    return "\n".join(linhas)


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


def _exec_aplicar_base(a: dict, matricula, senha, log, modo_teste=False,
                       iniciar_do_zero=False) -> str:
    from bot.services import desmembramento_service as ds

    r = ds.aplicar_base(a["chamados"], a["base"], matricula, senha, log=log,
                        iniciar_do_zero=iniciar_do_zero, origem="ui")
    if not r.get("ok"):
        return f"❌ Não rodou: {r.get('erro', 'erro desconhecido')}"
    linhas = [f"**Base {a['base']}** — {r['concluidos']} de {r['total']} chamado(s)."]
    for d in r["detalhe"]:
        feito = d["status"] == "concluido"
        linhas.append(f"- {_ok_falha(feito)} {d['chamado']}" + ("" if feito else f" ({d['status']})"))
    return "\n".join(linhas)


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

    linhas = [f"**Requisições:** {len(reqs)}"]
    for i, r in enumerate(reqs[:15], 1):
        partes = [str(r.get(c) or "") for c in ("usuario_afetado", "resumo", "item", "item_b")]
        atrib = r.get("usuario_atribuido") or r.get("grupo_atribuido") or ""
        linhas.append(f"{i}. {' · '.join(p for p in partes if p)}"
                      + (f" → {atrib}" if atrib else ""))
    if len(reqs) > 15:
        linhas.append(f"… e mais {len(reqs) - 15}")
    comum = reqs[0]
    if comum.get("descricao"):
        linhas.append(f"**Descrição (1ª):** {comum['descricao']}")
    return Acao(
        ferramenta="criar_requisicoes",
        args={"texto": texto},
        titulo="Requisição de Serviço",
        linhas=linhas,
        escreve=True,
        pode_simular=True,
        checkpoint=estado,
        aviso=aviso,
    )


def _exec_requisicoes(a: dict, matricula, senha, log, modo_teste=False,
                      iniciar_do_zero=False) -> str:
    """Mesmo laço do state/requisicao_state.py, com o mesmo checkpoint: se
    parar no meio, rodar de novo (aqui ou na página) continua de onde parou.
    No modo simulação o checkpoint não é tocado — nada foi criado."""
    from services import checkpoint as cp
    from services.browser_pw import NavegadorPW, _fazer_login_pw
    from services.flow_requisicao_pw import (
        _chave_checkpoint, criar_requisicao, parse_entrada,
    )

    texto = a["texto"]
    reqs = parse_entrada(texto)
    total = len(reqs)
    chave = _chave_checkpoint(texto)
    feitas = {}
    if not modo_teste:
        if cp.foi_concluido(chave):
            return "Este lote já foi criado antes — nada a fazer."
        if cp.existe_pendente(chave):
            feitas = {l["index"]: l for l in cp.status_linhas(chave)
                      if l["status"] == cp.STATUS_CONCLUIDO}
        else:
            cp.inicializar(chave, total, fluxo="requisicao", origem="ui",
                           matricula=matricula,
                           referencias=[r.get("usuario_afetado", "") for r in reqs])

    resultado = []
    with NavegadorPW(log) as page:
        if not _fazer_login_pw(page, matricula, senha, log):
            return "❌ Falha no login do Assyst."
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
    return "\n".join([f"{cab} — {ok} de {total}."] + resultado + rodape)


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


def _exec_lote(funcao: Callable, titulo: str, com_texto: bool):
    def executar(a: dict, matricula, senha, log, modo_teste=False,
                 iniciar_do_zero=False) -> str:
        if com_texto:
            r = funcao(a["chamados"], a["texto"], matricula, senha, log=log,
                       modo_teste=modo_teste)
        else:
            r = funcao(a["chamados"], matricula, senha, log=log, modo_teste=modo_teste)
        ok = sum(1 for v in r.values() if v[0])
        cab = f"**{titulo}{' (simulação, nada salvo)' if modo_teste else ''}** — {ok} de {len(r)}."
        linhas = [cab]
        for numero, v in r.items():
            detalhe = f" — {v[1]}" if not v[0] and v[1] else ""
            linhas.append(f"- {_ok_falha(v[0])} {numero}{detalhe}")
        return "\n".join(linhas)
    return executar


def _exec_atendimento(a, matricula, senha, log, modo_teste=False, iniciar_do_zero=False):
    from bot.services.atendimento_service import iniciar_lote
    return _exec_lote(iniciar_lote, "Iniciar Atendimento", False)(
        a, matricula, senha, log, modo_teste)


def _exec_informacao(a, matricula, senha, log, modo_teste=False, iniciar_do_zero=False):
    from bot.services.informacao_service import adicionar_lote
    return _exec_lote(adicionar_lote, "Adicionar Informação", True)(
        a, matricula, senha, log, modo_teste)


def _exec_fornecedor(a, matricula, senha, log, modo_teste=False, iniciar_do_zero=False):
    from bot.services.fornecedor_service import aguardar_lote
    return _exec_lote(aguardar_lote, "Aguardando Info do Fornecedor", True)(
        a, matricula, senha, log, modo_teste)


def _exec_usuario(a, matricula, senha, log, modo_teste=False, iniciar_do_zero=False):
    from bot.services.usuario_service import aguardar_lote
    return _exec_lote(aguardar_lote, "Aguardando Info do Usuário", True)(
        a, matricula, senha, log, modo_teste)


# --------------------------------------------------------------------------- #
# Só leitura — Minha Fila e SLA
# --------------------------------------------------------------------------- #

def _prep_fila(args: dict) -> "Acao | str":
    return Acao(ferramenta="consultar_minha_fila", args={}, titulo="Minha Fila",
                linhas=[], escreve=False)


def _exec_fila(a, matricula, senha, log, modo_teste=False, iniciar_do_zero=False):
    from bot.services.minhafila_service import consultar_fila
    fila = consultar_fila(matricula, senha, log=log)
    if fila is None:
        return "❌ Não consegui ler a sua fila (login ou tela que não carregou)."
    if not fila:
        return "Sua fila está vazia."
    linhas = [f"**Sua fila** — {len(fila)} chamado(s):"]
    for c in fila:
        linhas.append(f"- **{c.get('referencia', '')}** — {c.get('afetado', '')} · {c.get('secao', '')}")
    return "\n".join(linhas)


def _prep_sla(args: dict) -> "Acao | str":
    chamados = _lista(args.get("chamados"))
    if not chamados:
        return "Falta a lista de chamados para analisar."
    fila = args.get("fila") or FILA_PADRAO
    if fila not in FILAS:
        return f"Fila desconhecida: '{fila}'. Filas válidas: {', '.join(FILAS)}."
    return Acao(ferramenta="analisar_sla", args={"chamados": chamados, "fila": fila},
                titulo="Análise de SLA", linhas=[], escreve=False)


def _exec_sla(a, matricula, senha, log, modo_teste=False, iniciar_do_zero=False):
    from bot.services.sla_service import analisar_chamados
    r = analisar_chamados(a["chamados"], a["fila"], matricula, senha, log=log)
    linhas = [f"**SLA — fila {a['fila']}**"]
    for d in r:
        if not d["ok"]:
            linhas.append(f"- ❌ {d['numero']} — {d['erro']}")
            continue
        icone = "🔴" if d["estourado"] else "🟢"
        linhas.append(f"- {icone} **{d['numero']}** — {d['mensagem']} "
                      f"(gasto {d['tempo_gasto']}, resta {d['tempo_restante']})")
    return "\n".join(linhas)


# --------------------------------------------------------------------------- #
# Catálogo
# --------------------------------------------------------------------------- #

_CHAMADOS = {"type": "array", "items": {"type": "string"},
             "description": "Números dos chamados, ex.: ['1234567', 'R2472843']."}

FERRAMENTAS: dict[str, Ferramenta] = {f.nome: f for f in [
    Ferramenta(
        "listar_bases_conhecimento",
        "Lista as Bases de Conhecimento cadastradas no app (nomes exatos). Use "
        "antes de desmembrar/aplicar base quando não souber o nome exato.",
        {"type": "object", "properties": {
            "filtro": {"type": "string", "description": "Trecho do nome para filtrar (opcional)."}}},
        preparar=lambda a: "", local=_local_bases,
    ),
    Ferramenta(
        "desmembrar",
        "Desmembramento: cria um chamado FILHO por tombo a partir de um chamado "
        "PAI. Com 'base', também aplica a Base de Conhecimento em cada filho "
        "(Criar + Base); sem 'base', só cria (Só Criar).",
        {"type": "object", "properties": {
            "chamado_pai": {"type": "string"},
            "tombos": {"type": "array", "items": {"type": "string"},
                       "description": "Um filho por tombo."},
            "descricao": {"type": "string",
                          "description": "Descrição dos filhos. Use {{tombo}} onde o "
                                         "número do tombo deve entrar."},
            "base": {"type": "string", "description": "Nome da Base de Conhecimento (opcional)."},
        }, "required": ["chamado_pai", "tombos", "descricao"]},
        preparar=_prep_desmembrar, executar=_exec_desmembrar,
    ),
    Ferramenta(
        "aplicar_base",
        "Só Base: aplica uma Base de Conhecimento em chamados que JÁ existem.",
        {"type": "object", "properties": {
            "chamados": _CHAMADOS,
            "base": {"type": "string", "description": "Nome da Base de Conhecimento."},
        }, "required": ["chamados", "base"]},
        preparar=_prep_aplicar_base, executar=_exec_aplicar_base,
    ),
    Ferramenta(
        "criar_requisicoes",
        "Abre Requisições de Serviço (chamados novos), uma por item da lista. "
        "Quando o técnico pedir várias iguais variando só um campo (ex.: um "
        "tombo por chamado), repita os demais campos em cada item. Nenhum "
        "campo pode conter ';'.",
        {"type": "object", "properties": {"requisicoes": {"type": "array", "items": {
            "type": "object", "properties": {
                "usuario_afetado": {"type": "string", "description": "Matrícula do usuário afetado."},
                "edificio": {"type": "string", "description": "Ex.: Fórum Clóvis Beviláqua."},
                "resumo": {"type": "string"},
                "descricao": {"type": "string"},
                "item": {"type": "string", "description": "Ex.: Computador."},
                "item_b": {"type": "string",
                           "description": "Tombo com '*' na frente (ex.: *333284) ou um valor de catálogo."},
                "categoria": {"type": "string", "description": "Ex.: Configuração."},
                "grupo_atribuido": {"type": "string", "description": "Ex.: 2N CATI FCB."},
                "usuario_atribuido": {"type": "string", "description": "Nome do técnico."},
            }, "required": ["usuario_afetado", "item"]}}},
         "required": ["requisicoes"]},
        preparar=_prep_requisicoes, executar=_exec_requisicoes,
    ),
    Ferramenta(
        "iniciar_atendimento",
        "Inicia o atendimento (agora) dos chamados informados.",
        {"type": "object", "properties": {"chamados": _CHAMADOS}, "required": ["chamados"]},
        preparar=_prep_lote("iniciar_atendimento", "Iniciar Atendimento", False),
        executar=_exec_atendimento,
    ),
    Ferramenta(
        "adicionar_informacao",
        "Adiciona o mesmo texto livre (ação 'Adicionar Informação') em vários chamados.",
        {"type": "object", "properties": {"chamados": _CHAMADOS, "texto": {"type": "string"}},
         "required": ["chamados", "texto"]},
        preparar=_prep_lote("adicionar_informacao", "Adicionar Informação", True),
        executar=_exec_informacao,
    ),
    Ferramenta(
        "aguardar_fornecedor",
        "Marca os chamados como 'Aguardando Info do Fornecedor', com um texto.",
        {"type": "object", "properties": {"chamados": _CHAMADOS, "texto": {"type": "string"}},
         "required": ["chamados", "texto"]},
        preparar=_prep_lote("aguardar_fornecedor", "Aguardando Info do Fornecedor", True),
        executar=_exec_fornecedor,
    ),
    Ferramenta(
        "aguardar_usuario",
        "Marca os chamados como 'Aguardando Info do Usuário', com um texto.",
        {"type": "object", "properties": {"chamados": _CHAMADOS, "texto": {"type": "string"}},
         "required": ["chamados", "texto"]},
        preparar=_prep_lote("aguardar_usuario", "Aguardando Info do Usuário", True),
        executar=_exec_usuario,
    ),
    Ferramenta(
        "consultar_minha_fila",
        "Lista os chamados na fila do técnico logado (só leitura).",
        {"type": "object", "properties": {}},
        preparar=_prep_fila, executar=_exec_fila,
    ),
    Ferramenta(
        "analisar_sla",
        "Calcula o SLA (tempo gasto/restante) dos chamados informados (só leitura).",
        {"type": "object", "properties": {
            "chamados": _CHAMADOS,
            "fila": {"type": "string", "enum": list(FILAS),
                     "description": f"Fila do SLA. Padrão: {FILA_PADRAO}."},
        }, "required": ["chamados"]},
        preparar=_prep_sla, executar=_exec_sla,
    ),
]}


def esquemas() -> list[dict]:
    return [
        {"type": "function", "function": {
            "name": f.nome, "description": f.descricao, "parameters": f.parametros}}
        for f in FERRAMENTAS.values()
    ]


def executar(acao: Acao, matricula: str, senha: str, log,
             modo_teste: bool = False, iniciar_do_zero: bool = False) -> str:
    f = FERRAMENTAS[acao.ferramenta]
    return f.executar(acao.args, matricula, senha, log, modo_teste, iniciar_do_zero)
