"""
services/agente/ferramentas/requisicao.py — Requisição de Serviço.

Criar requisições (lote escrito pela IA ou colado de volta no chat), por
tombo (a IA identifica o TIPO e extrai os dados; o código expande uma linha
por tombo e confere os nomes no banco de referência) e os plantões do fim
de semana. Todas rodam pelo mesmo fluxo da página de Requisição.
"""

import datetime
import re

from services.agente.ferramentas.base import (
    Acao,
    Ferramenta,
    _conferir,
    _lista,
    _lista_curta,
    _resolver_nome,
    _sem_acento,
    normalizar_tombo,
)
from services.agente.sessao import Resultado, Sessao
from services.regras.requisicao_campos import ORDEM_COLUNAS, POR_CHAVE, SEPARADOR
from services.regras.sla_engine import FILAS


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


def _prep_requisicoes_ia(args: dict) -> "Acao | str":
    """criar_requisicoes pedido pela IA: confere técnico, fila, edifício,
    item e categoria de cada linha no banco (28/10) e cai no preparo comum.
    O lote colado de volta (requisicoes_coladas) NÃO passa aqui: é o texto
    exato de antes, e mudar um valor mudaria a chave do checkpoint."""
    confirmados = _lista(args.get("confirmados"))
    avisos: list[str] = []
    reqs = []
    for r in args.get("requisicoes") or []:
        r = dict(r)
        # Técnico e fila vêm inteiros do Assyst: fora do banco não passa
        # (mesma regra da Requisição por tombo). Item e categoria aceitam o
        # que o técnico confirmar; edifício só avisa.
        for chave, campo, aceita in (("usuario_atribuido", "tecnico", None),
                                     ("grupo_atribuido", "fila", None),
                                     ("edificio", "edificio", None),
                                     ("item", "item", confirmados),
                                     ("categoria", "categoria", confirmados)):
            if str(r.get(chave) or "").strip():
                r[chave], erro = _conferir(campo, str(r[chave]), avisos, aceita,
                                           brando=campo == "edificio")
                if erro:
                    return erro
        reqs.append(r)
    base = _prep_requisicoes({"requisicoes": reqs})
    if isinstance(base, Acao):
        avisos = list(dict.fromkeys(avisos))
        base.aviso = " ".join(avisos + ([base.aviso] if base.aviso else []))
    return base


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

def _quando_usar() -> str:
    """Itens e categorias do banco com os exemplos da equipe — a IA escolhe
    por convenção, não pelo nome (28/10)."""
    from services.dados import referencia

    def bloco(campo: str) -> str:
        return "; ".join(l["valor"] + (f" ({l['quando_usar']})" if l.get("quando_usar") else "")
                         for l in referencia.itens() if l.get("campo") == campo)
    return (f"\nItens: {bloco('item')}.\nCategorias: {bloco('categoria')}.\n"
            "Escolha pelos exemplos; se nenhum bater com o pedido, pergunte ao técnico.")


def _opcoes() -> dict[str, list[str]]:
    # Tudo do banco de referência (conhecimento/referencia/); os Presets do
    # SQLite saíram em 28/10.
    from services.dados import referencia
    return {"tecnicos": referencia.tecnicos(), "filas": list(FILAS),
            "edificios": referencia.nomes_edificios(),
            "itens": referencia.valores("item")}


def _tecnico_da_req(dito: str, opcoes: list[str], rotulo: str = "O técnico") -> tuple[str, str]:
    """(nome, erro) do técnico da Requisição: primeiro pelo banco de técnicos
    (mesma regra da atribuição: cada palavra é começo de palavra do nome),
    depois pela lista de técnicos (nome com/sem acento)."""
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
    return (
        "Abre Requisições de Serviço, uma por tombo (o sistema monta cada uma). "
        "Use para pedidos com tombos ou de um tipo de solicitação da base."
        # Técnicos e filas saíram (06/10): o código resolve nome parcial e,
        # se ambíguo/desconhecido, devolve as opções para o modelo perguntar.
        # Edifícios saíram em 28/10: o banco tem ~70 nomes, peso demais em
        # todo pedido; o código confere e, fora da lista, só avisa.
        + _quando_usar()
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
    confirmados = _lista(args.get("confirmados"))
    avisos = [a for a in (_aviso_fila(tecnico, fila),) if a]
    if args.get("fila") and _sem_acento(args["fila"]) != _sem_acento(fila):
        avisos.append(f"Fila: '{args['fila']}' → '{fila}'.")
    # Edifício: a lista do banco ainda é incompleta — fora dela só avisa.
    edificio, erro = _conferir("edificio", args["edificio"], avisos, brando=True)
    if erro:
        return erro

    tipo = None
    if args.get("tipo"):
        tipo = next((t for t in conhecimento.tipos()
                     if _sem_acento(t.nome) == _sem_acento(args["tipo"])), None)
    item = (args.get("item") or (tipo.item if tipo else "")).strip()
    if not item:
        return "Não consegui deduzir o Item. Pergunte ao técnico."
    # Item e Categoria, ditos ou vindos do tipo, conferidos no banco: um tipo
    # desatualizado na base também cai aqui (28/10).
    item, erro = _conferir("item", item, avisos, confirmados)
    if erro:
        return erro
    categoria = (args.get("categoria") or (tipo.categoria if tipo else "Instalar / Configurar")).strip()
    categoria, erro = _conferir("categoria", categoria, avisos, confirmados)
    if erro:
        return erro
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


# Catálogo deste arquivo (o __init__ junta todos, na ordem de _ORDEM).
FERRAMENTAS: list[Ferramenta] = [
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
            }, "required": ["usuario_afetado", "item"]}},
            "confirmados": {"type": "array", "items": {"type": "string"}, "description":
                            "Campos fora da referência que o técnico confirmou."}},
         "required": ["requisicoes"]},
        preparar=_prep_requisicoes_ia, executar=_exec_requisicoes,
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
            "confirmados": {"type": "array", "items": {"type": "string"}, "description":
                            "Campos fora da referência que o técnico confirmou."},
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
]
