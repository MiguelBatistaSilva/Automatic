"""
services/plantoes.py — Plantões Judiciários (18/11).

As regras dos plantões (antes só no agente, em ferramentas/requisicao.py) e a
ESCALA da página Plantões Judiciários, com o Sentinela que cria as Requisições.

Regras (do líder, 13/10): por dia, 3 Requisições — Sede Judiciária, Fórum
Clóvis Beviláqua e Custódia (edifício Externo) —, um técnico por local, mesma
descrição, item e categoria; usuário afetado = matrícula do SUPERVISOR (fica no
app_config, muda com a gestão). 23/11: mais 7 NACs do interior (08:00 as 14:00,
fila do Polo), também Requisição, no nome do supervisor DOS NACs. A página e o agente montam as linhas AQUI, então
o mesmo plantão dá o mesmo texto e a mesma chave de checkpoint nos dois.

Escala: em app_config['plantoes_escala'] (JSON) para o Sentinela, que roda no
backend (lifespan em automatic_app.py), achar sem a página aberta. Dias passados
= escala nova (próximo sáb/dom, sem técnicos).

Dias (19/11): sábado e domingo são FIXOS. Feriado colado no fim de semana
(sexta, quinta... antes; segunda, terça... depois) entra sozinho: os calculados
(nacionais, Páscoa, Ceará, Fortaleza) e os extras que o técnico cadastra na
página (portaria, ponto facultativo). Feriado no meio da semana: o técnico
adiciona o dia na mão. Dia tirado na mão não volta sozinho (e['removidos']).

Sentinela ("Inicia às", 19/11): na VÉSPERA do 1º dia do plantão, na hora
configurada (padrão 14:00; sexta feriado -> quinta). Desde 24/11 por BLOCO
(Capital e Interior, independentes): bloco completo -> cria; incompleto ->
avisa (página e Telegram) uma vez e cria assim que completar. Antes da hora,
nada. Depois de começar a criar, o bloco trava (mudar mudaria a chave do
checkpoint e criaria em dobro) e os dias travam para todos. Erro no meio:
"Tentar de novo" do bloco retoma pelo checkpoint. Dias passados = escala nova
sozinha (o botão "Nova escala" saiu em 24/11).
Roda na máquina de quem ligou, com o login do app.
"""

import datetime
import json
import logging
import threading
import time

from services.dados import db

log = logging.getLogger("plantoes")

# (chave, nome na página, edifício, onde na descrição, horário, fila)
# Cada local tem a SUA fila (19/11: sem seletor de fila na página).
CAPITAL = (
    ("sede", "Sede Judiciária (TJCE)", "Sede Judiciária", "no TJCE", "08:00 as 18:00", "2N CATI TJ"),
    ("forum", "Fórum Clóvis Beviláqua", "Fórum Clóvis Beviláqua", "no Fórum", "08:00 as 18:00", "2N CATI FCB"),
    ("custodia", "Custódia", "Externo", "na Custódia", "08:00 as 14:00", "2N CATI Vara de Custódia"),
)


def _nac(chave: str, cidade: str, nome_edificio: str, polo: str) -> tuple:
    edificio = f"NAC {nome_edificio} - Núcleo de Audiência de Custódia"
    return (chave, f"NAC {cidade}", edificio, f"na {edificio}", "08:00 as 14:00",
            f"2N CATI Polo {polo}")


# NACs do interior (23/11): também Requisição (R), como a capital (antes eram
# abertos como "Reuniões e Eventos", S). Usuário afetado = supervisor dos NACs.
NACS = (
    _nac("nac_juazeiro", "Juazeiro", "Juazeiro do Norte", "Juazeiro"),
    _nac("nac_quixada", "Quixadá", "Quixadá", "Quixadá"),
    _nac("nac_iguatu", "Iguatu", "Iguatu", "Iguatu"),
    _nac("nac_crateus", "Crateús", "Crateús", "Crateús"),
    _nac("nac_sobral", "Sobral", "Sobral", "Sobral"),
    _nac("nac_maracanau", "Maracanaú", "Maracanaú", "Maracanaú"),
    _nac("nac_caucaia", "Caucaia", "Caucaia", "Caucaia"),
)
LOCAIS = CAPITAL + NACS
CHAVES_NAC = frozenset(c for c, *_ in NACS)
# Blocos independentes (24/11): cada um é criado quando ele mesmo fica completo.
GRUPOS = {"capital": CAPITAL, "interior": NACS}
NOME_GRUPO = {"capital": "Capital", "interior": "Interior"}


def grupo_do(local: str) -> str:
    return "interior" if local in CHAVES_NAC else "capital"
SEMANA = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")
SEMANA_LONGA = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")
# "Inicia às" (19/11): os chamados saem na VÉSPERA do 1º dia, nesta hora.
HORA_FIXA_PADRAO = {"hora": "14:00"}

_CHAVE = "plantoes_escala"
_CHAVE_SUPERVISOR = "plantao_supervisor"            # capital
_CHAVE_SUPERVISOR_NAC = "plantao_supervisor_nac"    # NACs (23/11)
_CHECAGEM_S = 30
CRIANDO, CONCLUIDO, ERRO = "criando", "concluido", "erro"


# --------------------------------------------------------------------------- #
# Regras
# --------------------------------------------------------------------------- #

def supervisor(nac: bool = False) -> str:
    """Matrícula do usuário afetado: o supervisor da capital ou o dos NACs."""
    r = db.consultar("SELECT valor FROM app_config WHERE chave = ?",
                     (_CHAVE_SUPERVISOR_NAC if nac else _CHAVE_SUPERVISOR,))
    return r[0]["valor"] if r else ""


def salvar_supervisor(matricula: str, nac: bool = False) -> None:
    with db.transacao() as con:
        con.execute("INSERT OR REPLACE INTO app_config VALUES (?, ?)",
                    (_CHAVE_SUPERVISOR_NAC if nac else _CHAVE_SUPERVISOR, matricula))


# --------------------------------------------------------------------------- #
# Feriados
# --------------------------------------------------------------------------- #

_CHAVE_EXTRAS = "plantoes_dias_extras"
_UM = datetime.timedelta(days=1)

_FIXOS = {
    (1, 1): "Confraternização Universal",
    (3, 19): "São José (CE)",
    (3, 25): "Data Magna do Ceará",
    (4, 21): "Tiradentes",
    (5, 1): "Dia do Trabalho",
    (8, 15): "N. Sra. da Assunção (Fortaleza)",
    (9, 7): "Independência",
    (10, 12): "N. Sra. Aparecida",
    (11, 2): "Finados",
    (11, 15): "Proclamação da República",
    (11, 20): "Consciência Negra",
    (12, 25): "Natal",
}
# dias a partir do domingo de Páscoa
_MOVEIS = {-48: "Carnaval", -47: "Carnaval", -3: "Quinta-feira Santa",
           -2: "Sexta-feira Santa", 60: "Corpus Christi"}


def _pascoa(ano: int) -> datetime.date:
    """Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher)."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 19 * l) // 433
    mes = (h + l - 7 * m + 90) // 25
    return datetime.date(ano, mes, (h + l - 7 * m + 33 * mes + 19) % 32)


def dias_extras() -> dict:
    """Os cadastrados na página: {iso: nome}."""
    r = db.consultar("SELECT valor FROM app_config WHERE chave = ?", (_CHAVE_EXTRAS,))
    try:
        return dict(json.loads(r[0]["valor"])) if r else {}
    except (ValueError, TypeError):
        return {}


def _gravar_extras(extras: dict) -> None:
    with db.transacao() as con:
        con.execute("INSERT OR REPLACE INTO app_config VALUES (?, ?)",
                    (_CHAVE_EXTRAS, json.dumps(dict(sorted(extras.items())), ensure_ascii=False)))


def feriados(anos) -> dict:
    """{data: nome} dos calculados + extras dos anos pedidos."""
    anos = set(anos)
    out = {}
    for ano in anos:
        out.update({datetime.date(ano, m, d): n for (m, d), n in _FIXOS.items()})
        p = _pascoa(ano)
        out.update({p + datetime.timedelta(days=k): n for k, n in _MOVEIS.items()})
    for iso, n in dias_extras().items():
        d = datetime.date.fromisoformat(iso)
        if d.year in anos:
            out[d] = n
    return out


def _cadeia(sabado: datetime.date, hoje: datetime.date) -> list:
    """Sábado, domingo e os feriados colados neles (antes, só de hoje em diante)."""
    fer = feriados({sabado.year - 1, sabado.year, sabado.year + 1})
    dias = [sabado, sabado + _UM]
    d = sabado - _UM
    while d >= hoje and d in fer:
        dias.insert(0, d)
        d -= _UM
    d = sabado + 2 * _UM
    while d in fer:
        dias.append(d)
        d += _UM
    return dias


def proximo_fim_de_semana(hoje: datetime.date) -> list:
    """Sábado e domingo que vêm (sábado hoje = este), com os feriados colados."""
    return _cadeia(hoje + datetime.timedelta(days=(5 - hoje.weekday()) % 7), hoje)


def adicionar_extra(dia: datetime.date, nome: str) -> str:
    """'Adicionar dias' da página (19/11: substituiu o 'Adicionar dia'). O dia
    fica cadastrado e entra sozinho na escala certa: colado no fim de semana,
    nele; no meio da semana, na escala do sábado anterior (ver _completar)."""
    if dia < datetime.date.today():
        return "Essa data já passou."
    if _desfazer_remocao(dia.isoformat()):
        return ""   # dia tirado no X: volta para a escala
    extras = dias_extras()
    if dia.isoformat() in extras:
        return "Esse dia já está cadastrado."
    nome = ((nome or "").strip()
            or feriados({dia.year}).get(dia) or "Sem expediente")
    extras[dia.isoformat()] = nome
    _gravar_extras(extras)
    e = estado()
    sab = _sabado_da_escala(e)
    if (_travada(e) and sab and dia.isoformat() not in e["dias"]
            and sab <= dia < sab + 7 * _UM):
        return ("Cadastrado, mas a escala deste fim de semana já foi criada: "
                "abra a Requisição desse dia à mão.")
    return ""


def _desfazer_remocao(iso: str) -> bool:
    """Tira o dia de e['removidos'] e deixa o _completar trazê-lo de volta
    (feriado colado ou cadastrado no meio da semana). True se voltou."""
    with db.transacao() as con:
        e = _ler(con)
        if _travada(e) or iso not in (e.get("removidos") or []):
            return False
        e["removidos"].remove(iso)
        _completar(e, datetime.date.today())
        _gravar(con, e)
        return iso in e["dias"]


def remover_extra(iso: str) -> None:
    """Descadastra; se o dia já estava na escala (e ela não foi criada), sai dela."""
    extras = dias_extras()
    if extras.pop(iso, None) is None:
        return
    _gravar_extras(extras)
    if datetime.date.fromisoformat(iso).weekday() < 5:
        remover_dia(iso)


def montar(datas: list[datetime.date], quem: list[dict], matricula: str,
           matricula_nac: str = "") -> list[dict]:
    """As Requisições: `quem[i][local]` = técnico do dia i; a fila é a do
    local. Ordem = a da lista do líder: todos os dias da Sede, depois Fórum,
    depois Custódia, depois os NACs. Só entram os locais presentes em `quem`
    (o agente ainda passa só os 3 da capital). Os NACs usam `matricula_nac`."""
    return [
        {"usuario_afetado": matricula_nac if chave in CHAVES_NAC else matricula,
         "edificio": edificio,
         "resumo": "Requisição de Serviço",
         "descricao": (f"Solicito acompanhamento técnico ao Plantão Judiciário que "
                       f"ocorrerá {onde} no dia {data:%d/%m/%Y}. Horário {horario}"),
         "item": "Apoio a Eventos e Audiências", "item_b": "IC NÃO LOCALIZADO",
         "categoria": "Apoio Técnico em Evento ou Reunião",
         "grupo_atribuido": fila,
         "usuario_atribuido": quem[i][chave]}
        for chave, _, edificio, onde, horario, fila in LOCAIS
        if quem and all(chave in q for q in quem)
        for i, data in enumerate(datas)
    ]


def rotulo_dia(d: datetime.date) -> str:
    return f"{SEMANA[d.weekday()]} {d:%d/%m}"
# --------------------------------------------------------------------------- #
# Escala (banco)
# --------------------------------------------------------------------------- #
# Blocos independentes (24/11): Capital e Interior têm, cada um, a sua fase
# (criando/concluído/erro), o seu resumo e o seu aviso de incompleta, em
# e['blocos'][grupo]. O Sentinela cria o bloco que estiver completo; o outro
# espera completar. Compartilhados (e['sentinela']): ligado, "Inicia às",
# matrícula de quem ligou. Os DIAS também são de todos: travam assim que
# qualquer bloco começa a ser criado.

def _bloco_vazio() -> dict:
    return {"fase": "", "resumo": "", "avisou_incompleto": False, "quando": ""}


def _nova(dias: list[datetime.date], sentinela: "dict | None" = None) -> dict:
    s = {k: v for k, v in (sentinela or {}).items()
         if k in ("ligado", "hora_fixa", "matricula")}
    s.setdefault("ligado", False)
    s.setdefault("hora_fixa", dict(HORA_FIXA_PADRAO))
    return {"dias": [d.isoformat() for d in dias],
            "escala": {c: {d.isoformat(): {"tecnico": ""} for d in dias}
                       for c, *_ in LOCAIS},
            "sentinela": s,
            "blocos": {g: _bloco_vazio() for g in GRUPOS}}


def _ler(con) -> dict:
    r = con.execute("SELECT valor FROM app_config WHERE chave = ?", (_CHAVE,)).fetchone()
    try:
        e = json.loads(r["valor"]) if r else None
    except (ValueError, KeyError):
        e = None
    hoje = datetime.date.today()
    if not e or not e.get("dias") or max(e["dias"]) < hoje.isoformat():
        e = _nova(proximo_fim_de_semana(hoje), (e or {}).get("sentinela"))
        _gravar(con, e)
    elif _migrar_blocos(e) | _novos_locais(e) | _completar(e, hoje):
        _gravar(con, e)
    return e


def _migrar_blocos(e: dict) -> bool:
    """Escala de antes dos blocos (24/11): a fase única era a da capital."""
    if "blocos" in e:
        return False
    s = e["sentinela"]
    cap = _bloco_vazio()
    cap.update({k: s.pop(k) for k in ("fase", "resumo", "avisou_incompleto", "quando")
                if k in s})
    e["blocos"] = {"capital": cap, "interior": _bloco_vazio()}
    return True


def _novos_locais(e: dict) -> bool:
    """Escala gravada antes de um local existir (NACs, 23/11): entra vazio,
    se o bloco dele ainda não começou (mudar a lista criaria em dobro)."""
    novos = [c for c, *_ in LOCAIS
             if c not in e["escala"] and not _travado(e, grupo_do(c))]
    for c in novos:
        e["escala"][c] = {d: {"tecnico": ""} for d in e["dias"]}
    return bool(novos)


def _completar(e: dict, hoje: datetime.date) -> bool:
    """Garante sáb/dom e os feriados colados (escala antiga, extra cadastrado
    depois). Não mexe em escala travada nem devolve dia tirado na mão."""
    if _travada(e):
        return False
    sab = _sabado_da_escala(e)
    if not sab:
        return False
    fora = set(e.get("removidos") or [])
    # Cadastrados no meio da semana: vão para a escala do sábado anterior.
    meio = [datetime.date.fromisoformat(iso) for iso in dias_extras()]
    meio = [d for d in meio if sab + _UM < d < sab + 7 * _UM and d >= hoje]
    novos = [d for d in dict.fromkeys(_cadeia(sab, hoje) + meio)
             if d.isoformat() not in e["dias"]
             and (d.weekday() >= 5 or d.isoformat() not in fora)]
    for d in novos:
        _incluir(e, d)
    if novos:
        _recalcular(e)
    return bool(novos)


def _sabado_da_escala(e: dict) -> "datetime.date | None":
    ds = datas(e)
    sab = [d for d in ds if d.weekday() == 5] or [d - _UM for d in ds if d.weekday() == 6]
    return sab[0] if sab else None


def _incluir(e: dict, d: datetime.date) -> None:
    iso = d.isoformat()
    e["dias"] = sorted(e["dias"] + [iso])
    for c in e["escala"]:
        e["escala"][c][iso] = {"tecnico": ""}
    if iso in (e.get("removidos") or []):
        e["removidos"].remove(iso)


def _gravar(con, e: dict) -> None:
    con.execute("INSERT OR REPLACE INTO app_config VALUES (?, ?)",
                (_CHAVE, json.dumps(e, ensure_ascii=False)))


def estado() -> dict:
    with db.transacao() as con:
        return _ler(con)


def datas(e: dict) -> list[datetime.date]:
    return [datetime.date.fromisoformat(d) for d in e["dias"]]


def _locais_da(e: dict, grupo: str = "") -> list[tuple]:
    """Os locais que esta escala tem (do grupo, se pedido). Uma escala travada
    antes dos NACs não os tem."""
    return [l for l in (GRUPOS[grupo] if grupo else LOCAIS) if l[0] in e["escala"]]


def faltando(e: dict, grupo: str) -> list[str]:
    """O que falta para o bloco ficar completo ([] = nada)."""
    nac = grupo == "interior"
    falta = [] if supervisor(nac=nac) else [
        "matrícula do supervisor " + ("dos NACs" if nac else "da capital")]
    for chave, nome, *_ in _locais_da(e, grupo):
        for d in datas(e):
            cel = e["escala"][chave].get(d.isoformat()) or {}
            if not cel.get("tecnico"):
                falta.append(f"{nome.split(' (')[0]} {rotulo_dia(d)}")
    return falta


def requisicoes(e: dict, grupo: str) -> list[dict]:
    ds = datas(e)
    quem = [{c: e["escala"][c][d.isoformat()]["tecnico"] for c, *_ in _locais_da(e, grupo)}
            for d in ds]
    return montar(ds, quem, supervisor(), supervisor(nac=True))


def referencias(e: dict, grupo: str) -> list[str]:
    """Rótulo de cada Requisição para o Meus fluxos, na ordem do montar:
    'NAC Caucaia · sáb 28/11'."""
    return [f"{nome.split(' (')[0]} · {rotulo_dia(d)}"
            for _, nome, *_ in _locais_da(e, grupo) for d in datas(e)]


def resultados(e: dict, grupo: str) -> list[dict]:
    """Tabela "Resultados" da página (24/11): uma linha por Requisição do
    bloco, com o número lido do checkpoint do lote (mesma chave que a criação
    usa: o hash do texto). Vazia antes de criar; as linhas entram com o fluxo."""
    from services.agente.ferramentas.requisicao import _texto_requisicoes
    from services.dados import checkpoint as cp
    from services.fluxos.flow_requisicao_pw import _chave_checkpoint

    reqs = requisicoes(e, grupo)
    if not reqs:
        return []
    feitas = {}
    try:
        chave = _chave_checkpoint(_texto_requisicoes(reqs))
        feitas = {l["index"]: l for l in cp.status_linhas(chave)
                  if l.get("status") == cp.STATUS_CONCLUIDO}
    except Exception:
        log.exception("Plantões: falha ao ler o checkpoint")
    # As linhas ENTRAM conforme o fluxo anda (como na Requisição de Serviço):
    # antes de criar, vazia. O laço é em ordem, então uma linha sem número
    # ANTES da última criada já foi tentada e falhou; no fim (concluído/erro),
    # todas as que não saíram são "Não criado".
    fase = e["blocos"][grupo].get("fase")
    if fase == CONCLUIDO or fase == ERRO:
        ate = len(reqs)
    elif fase == CRIANDO and feitas:
        ate = max(feitas) + 1
    else:
        ate = 0
    out = []
    for i, (ref, r) in enumerate(zip(referencias(e, grupo), reqs)):
        if i >= ate and i not in feitas:
            continue
        if i in feitas:
            status, numero, cor = "Criado", feitas[i].get("numero", ""), "green"
        else:
            status, numero, cor = "Não criado", "--", "red"
        out.append({"local": ref, "tecnico": r.get("usuario_atribuido") or "--",
                    "numero": numero, "status": status, "cor": cor})
    return out


def momento_fixo(e: dict) -> datetime.datetime:
    """Quando inicia: véspera do 1º dia do plantão (sexta-feira feriado: a
    quinta), na hora configurada."""
    hf = e["sentinela"].get("hora_fixa") or HORA_FIXA_PADRAO
    d = min(datas(e)) - _UM
    h, m = (int(x) for x in str(hf["hora"]).split(":"))
    return datetime.datetime(d.year, d.month, d.day, h, m)


def _travado(e: dict, grupo: str) -> bool:
    return e["blocos"][grupo].get("fase") in (CRIANDO, CONCLUIDO, ERRO)


def _travada(e: dict) -> bool:
    """Algum bloco começou: os DIAS (de todos) não mudam mais."""
    return any(_travado(e, g) for g in GRUPOS)


def _recalcular(e: dict, grupo: str = "") -> None:
    """Depois de qualquer mudança na escala: o aviso de incompleta pode voltar."""
    for g in ([grupo] if grupo else GRUPOS):
        e["blocos"][g]["avisou_incompleto"] = False


def _mudar(fn, grupo: str = "") -> str:
    """Aplica `fn(e)` numa transação. Devolve '' ou o motivo de não poder.
    Com `grupo`, só aquele bloco precisa estar livre; sem, todos (os dias)."""
    with db.transacao() as con:
        e = _ler(con)
        if _travado(e, grupo) if grupo else _travada(e):
            return ("A criação deste bloco já começou: ele não muda mais." if grupo else
                    "A criação já começou: os dias não mudam mais.")
        erro = fn(e)
        if erro:
            return erro
        _recalcular(e, grupo)
        _gravar(con, e)
    return ""


def definir(local: str, dia: str, campo: str, valor: str) -> str:
    def fn(e):
        if campo != "tecnico" or local not in e["escala"]:
            return "Campo inválido."
        if dia not in e["escala"][local]:
            return "Dia fora da escala."
        e["escala"][local][dia][campo] = valor
    return _mudar(fn, grupo_do(local))


def remover_dia(iso: str) -> str:
    def fn(e):
        if iso not in e["dias"]:
            return "Dia fora da escala."
        if datetime.date.fromisoformat(iso).weekday() >= 5:
            return "Sábado e domingo são fixos."
        e["dias"].remove(iso)
        e.setdefault("removidos", []).append(iso)
        for c in e["escala"]:
            e["escala"][c].pop(iso, None)
    return _mudar(fn)


def definir_supervisor(matricula: str, nac: bool = False) -> str:
    """Só grava se o bloco dele não começou a ser criado."""
    grupo = "interior" if nac else "capital"
    with db.transacao() as con:
        e = _ler(con)
        if _travado(e, grupo):
            return ("A criação " + ("do Interior" if nac else "da Capital")
                    + " já começou: a matrícula não muda mais.")
        con.execute("INSERT OR REPLACE INTO app_config VALUES (?, ?)",
                    (_CHAVE_SUPERVISOR_NAC if nac else _CHAVE_SUPERVISOR, matricula))
        _recalcular(e, grupo)
        _gravar(con, e)
    return ""


# --------------------------------------------------------------------------- #
# Sentinela
# --------------------------------------------------------------------------- #

def ligar(matricula: str) -> None:
    with db.transacao() as con:
        e = _ler(con)
        e["sentinela"].update({"ligado": True, "matricula": matricula})
        _recalcular(e)
        _gravar(con, e)


def desligar() -> None:
    with db.transacao() as con:
        e = _ler(con)
        e["sentinela"]["ligado"] = False
        _gravar(con, e)


def definir_hora_fixa(hora: str) -> str:
    try:
        h, m = (int(x) for x in hora.split(":"))
        assert 0 <= h < 24 and 0 <= m < 60
    except Exception:
        return "Horário inválido."
    with db.transacao() as con:
        e = _ler(con)
        e["sentinela"]["hora_fixa"] = {"hora": f"{h:02d}:{m:02d}"}
        _recalcular(e)
        _gravar(con, e)
    return ""


def tentar_de_novo(grupo: str) -> None:
    """Depois de erro: cria o que faltou (o checkpoint pula as já criadas)."""
    with db.transacao() as con:
        e = _ler(con)
        if e["blocos"][grupo].get("fase") == ERRO:
            e["blocos"][grupo]["fase"] = ""
            _gravar(con, e)


def _pegar_vez(agora: float) -> "tuple[str, str, dict] | None":
    """('criar' | 'avisar', grupo, estado) ou None. Em transação: dois
    backends (hot-reload) nunca criam juntos. Um bloco por vez; o outro sai
    na volta seguinte do laço."""
    with db.transacao() as con:
        e = _ler(con)
        if not e["sentinela"].get("ligado") or agora < momento_fixo(e).timestamp():
            return None
        for g in GRUPOS:
            b = e["blocos"][g]
            if _travado(e, g):
                continue
            # Passou da hora: completo inicia já; incompleto avisa uma vez e
            # inicia assim que completar.
            if not faltando(e, g):
                b.update({"fase": CRIANDO, "resumo": "Criando as Requisições..."})
                _gravar(con, e)
                return "criar", g, e
            if not b.get("avisou_incompleto"):
                b["avisou_incompleto"] = True
                _gravar(con, e)
                return "avisar", g, e
    return None


def _concluir(grupo: str, fase: str, resumo: str) -> None:
    with db.transacao() as con:
        e = _ler(con)
        e["blocos"][grupo].update({"fase": fase, "resumo": resumo,
                                   "quando": datetime.datetime.now().strftime("%d/%m %H:%M")})
        _gravar(con, e)


# Log por bloco (24/11): o Sentinela roda no backend, fora da página; cada
# passo vai para o banco e a página lê enquanto está aberta. Fica até a
# próxima criação do mesmo bloco (para ver depois como foi).
_CHAVE_LOG = "plantoes_log"
_MAX_LOG = 500


def registrar(grupo: str, msg: str, tipo: str = "info") -> None:
    linha = {"ts": time.strftime("%d/%m %H:%M:%S"), "tipo": tipo, "msg": str(msg)}
    with db.transacao() as con:
        r = con.execute("SELECT valor FROM app_config WHERE chave = ?", (_CHAVE_LOG,)).fetchone()
        try:
            tudo = json.loads(r["valor"]) if r else {}
        except (ValueError, KeyError):
            tudo = {}
        tudo[grupo] = (tudo.get(grupo) or [])[-(_MAX_LOG - 1):] + [linha]
        con.execute("INSERT OR REPLACE INTO app_config VALUES (?, ?)",
                    (_CHAVE_LOG, json.dumps(tudo, ensure_ascii=False)))
    log.info("[%s] %s", grupo, msg)


def limpar_log(grupo: str) -> None:
    with db.transacao() as con:
        r = con.execute("SELECT valor FROM app_config WHERE chave = ?", (_CHAVE_LOG,)).fetchone()
        try:
            tudo = json.loads(r["valor"]) if r else {}
        except (ValueError, KeyError):
            tudo = {}
        tudo[grupo] = []
        con.execute("INSERT OR REPLACE INTO app_config VALUES (?, ?)",
                    (_CHAVE_LOG, json.dumps(tudo, ensure_ascii=False)))


def linhas_log(grupo: str) -> list[dict]:
    r = db.consultar("SELECT valor FROM app_config WHERE chave = ?", (_CHAVE_LOG,))
    try:
        return list((json.loads(r[0]["valor"]) if r else {}).get(grupo) or [])
    except (ValueError, TypeError):
        return []


def _telegram(matricula: str, texto: str) -> None:
    from services.agente import agendados
    r = db.consultar("SELECT chat_id FROM bot_credenciais WHERE matricula = ? LIMIT 1",
                     (matricula,))
    if r and r[0]["chat_id"] is not None:
        agendados._mandar_telegram(r[0]["chat_id"], texto)


def _criar(e: dict, grupo: str) -> None:
    from services.agente.ferramentas import requisicao
    from services.agente.sessao import Sessao
    from services.dados import credenciais

    limpar_log(grupo)
    registrar(grupo, f"Iniciando a criação dos plantões ({NOME_GRUPO[grupo]}).", "status")
    dono = e["sentinela"].get("matricula", "")
    matricula, senha = credenciais.carregar()
    if matricula != dono or not senha:
        registrar(grupo, "A credencial do app não é a de quem ligou o Sentinela.", "error")
        _concluir(grupo, ERRO, "A credencial do app não é a de quem ligou o Sentinela.")
        return
    acao = requisicao._prep_requisicoes({"requisicoes": requisicoes(e, grupo)})
    if isinstance(acao, str):
        registrar(grupo, acao, "error")
        _concluir(grupo, ERRO, acao)
        return
    # Meus fluxos: "Plantões · Capital/Interior", cada linha com local e dia.
    acao.args.update({"fluxo": f"plantoes_{grupo}", "referencias": referencias(e, grupo)})
    sessao = Sessao(matricula, senha, lambda m, t="info": registrar(grupo, m, t))
    try:
        res = requisicao._exec_requisicoes(acao.args, sessao)
        fase, texto = (CONCLUIDO if res.ok else ERRO), res.texto
    except Exception as ex:
        fase, texto = ERRO, f"❌ {ex or type(ex).__name__}"
        registrar(grupo, f"Erro: {ex or type(ex).__name__}", "error")
    finally:
        sessao.fechar()
    registrar(grupo, "Concluído." if fase == CONCLUIDO else "Parou com erro: confira o resultado.",
              "success" if fase == CONCLUIDO else "error")
    _concluir(grupo, fase, texto)
    dias = ", ".join(rotulo_dia(d) for d in datas(e))
    _telegram(dono, f"🛡️ Plantões Judiciários · {NOME_GRUPO[grupo]} ({dias})\n\n{texto}")


def _avisar_incompleto(e: dict, grupo: str) -> None:
    falta = faltando(e, grupo)
    texto = (f"Chegou o horário de criar os plantões ({NOME_GRUPO[grupo]}), mas a escala "
             "está incompleta. Falta: " + ", ".join(falta) + ". Inicia assim que completar.")
    with db.transacao() as con:
        e2 = _ler(con)
        e2["blocos"][grupo]["resumo"] = "⚠️ " + texto
        _gravar(con, e2)
    registrar(grupo, texto, "error")
    _telegram(e["sentinela"].get("matricula", ""), "🛡️ Plantões Judiciários\n\n⚠️ " + texto)


_ligado = False
_lock = threading.Lock()


def iniciar_vigia() -> None:
    """Liga o laço deste processo, uma vez só (thread própria: o Playwright sync
    se prende à thread que o abriu)."""
    global _ligado
    with _lock:
        if _ligado:
            return
        _ligado = True

    def laco():
        # Criação que caiu no meio (app fechado): vira erro, e "Tentar de novo"
        # retoma pelo checkpoint.
        try:
            with db.transacao() as con:
                e = _ler(con)
                mudou = False
                for b in e["blocos"].values():
                    if b.get("fase") == CRIANDO:
                        b.update({"fase": ERRO, "resumo":
                                  "O app fechou no meio da criação. Confira e tente de novo."})
                        mudou = True
                if mudou:
                    _gravar(con, e)
        except Exception:
            log.exception("Plantões: falha ao limpar o estado")
        while True:
            try:
                vez = _pegar_vez(time.time())
                if vez and vez[0] == "criar":
                    _criar(vez[2], vez[1])
                elif vez:
                    _avisar_incompleto(vez[2], vez[1])
            except Exception:
                log.exception("Falha no Sentinela dos plantões")
            time.sleep(_CHECAGEM_S)

    threading.Thread(target=laco, daemon=True, name="plantoes").start()
