"""
services/plantoes.py — Plantões Judiciários (18/11).

As regras dos plantões (antes só no agente, em ferramentas/requisicao.py) e a
ESCALA da página Plantões Judiciários, com o Sentinela que cria as Requisições.

Regras (do líder, 13/10): por dia, 3 Requisições — Sede Judiciária, Fórum
Clóvis Beviláqua e Custódia (edifício Externo) —, um técnico por local, mesma
descrição, item e categoria; usuário afetado = matrícula do SUPERVISOR (fica no
app_config, muda com a gestão). A página e o agente montam as linhas AQUI, então
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
configurada (padrão 14:00; sexta feriado -> quinta). Completa -> cria. Incompleta ->
avisa (página e Telegram) uma vez e cria assim que completar. Antes da hora, nada.
Depois de começar a criar, a escala trava (mudar mudaria a chave do checkpoint
e criaria em dobro). Erro no meio: "Tentar de novo" retoma pelo checkpoint.
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
LOCAIS = (
    ("sede", "Sede Judiciária (TJCE)", "Sede Judiciária", "no TJCE", "08:00 as 18:00", "2N CATI TJ"),
    ("forum", "Fórum Clóvis Beviláqua", "Fórum Clóvis Beviláqua", "no Fórum", "08:00 as 18:00", "2N CATI FCB"),
    ("custodia", "Custódia", "Externo", "na Custódia", "08:00 as 14:00", "2N CATI Vara de Custódia"),
)
SEMANA = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")
SEMANA_LONGA = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")
# "Inicia às" (19/11): os chamados saem na VÉSPERA do 1º dia, nesta hora.
HORA_FIXA_PADRAO = {"hora": "14:00"}

_CHAVE = "plantoes_escala"
_CHAVE_SUPERVISOR = "plantao_supervisor"
_CHECAGEM_S = 30
CRIANDO, CONCLUIDO, ERRO = "criando", "concluido", "erro"


# --------------------------------------------------------------------------- #
# Regras
# --------------------------------------------------------------------------- #

def supervisor() -> str:
    r = db.consultar("SELECT valor FROM app_config WHERE chave = ?", (_CHAVE_SUPERVISOR,))
    return r[0]["valor"] if r else ""


def salvar_supervisor(matricula: str) -> None:
    with db.transacao() as con:
        con.execute("INSERT OR REPLACE INTO app_config VALUES (?, ?)",
                    (_CHAVE_SUPERVISOR, matricula))


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


def montar(datas: list[datetime.date], quem: list[dict], matricula: str) -> list[dict]:
    """As Requisições: `quem[i][local]` = técnico do dia i; a fila é a do
    local. Ordem = a da lista do líder: todos os dias da Sede, depois Fórum,
    depois Custódia."""
    return [
        {"usuario_afetado": matricula, "edificio": edificio,
         "resumo": "Requisição de Serviço",
         "descricao": (f"Solicito acompanhamento técnico ao Plantão Judiciário que "
                       f"ocorrerá {onde} no dia {data:%d/%m/%Y}. Horário {horario}"),
         "item": "Apoio a Eventos e Audiências", "item_b": "IC NÃO LOCALIZADO",
         "categoria": "Apoio Técnico em Evento ou Reunião",
         "grupo_atribuido": fila,
         "usuario_atribuido": quem[i][chave]}
        for chave, _, edificio, onde, horario, fila in LOCAIS
        for i, data in enumerate(datas)
    ]


def rotulo_dia(d: datetime.date) -> str:
    return f"{SEMANA[d.weekday()]} {d:%d/%m}"


# --------------------------------------------------------------------------- #
# Escala (banco)
# --------------------------------------------------------------------------- #

def _nova(dias: list[datetime.date], sentinela: "dict | None" = None) -> dict:
    s = dict(sentinela or {})
    s.update({"fase": "", "resumo": "", "avisou_incompleto": False})
    s.setdefault("ligado", False)
    s.setdefault("hora_fixa", dict(HORA_FIXA_PADRAO))
    return {"dias": [d.isoformat() for d in dias],
            "escala": {c: {d.isoformat(): {"tecnico": ""} for d in dias}
                       for c, *_ in LOCAIS},
            "sentinela": s}


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
    elif _completar(e, hoje):
        _gravar(con, e)
    return e


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
    for c, *_ in LOCAIS:
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


def faltando(e: dict) -> list[str]:
    """O que falta para a escala ficar completa ('' de nada)."""
    falta = [] if supervisor() else ["matrícula do supervisor"]
    for chave, nome, *_ in LOCAIS:
        for d in datas(e):
            cel = e["escala"][chave].get(d.isoformat()) or {}
            if not cel.get("tecnico"):
                falta.append(f"{nome.split(' (')[0]} {rotulo_dia(d)}")
    return falta


def requisicoes(e: dict) -> list[dict]:
    ds = datas(e)
    quem = [{c: e["escala"][c][d.isoformat()]["tecnico"] for c, *_ in LOCAIS} for d in ds]
    return montar(ds, quem, supervisor())


def momento_fixo(e: dict) -> datetime.datetime:
    """Quando inicia: véspera do 1º dia do plantão (sexta-feira feriado: a
    quinta), na hora configurada."""
    hf = e["sentinela"].get("hora_fixa") or HORA_FIXA_PADRAO
    d = min(datas(e)) - _UM
    h, m = (int(x) for x in str(hf["hora"]).split(":"))
    return datetime.datetime(d.year, d.month, d.day, h, m)


def _travada(e: dict) -> bool:
    return e["sentinela"].get("fase") in (CRIANDO, CONCLUIDO, ERRO)


def _recalcular(e: dict) -> None:
    """Depois de qualquer mudança na escala: o aviso de incompleta pode voltar."""
    e["sentinela"]["avisou_incompleto"] = False


def _mudar(fn) -> str:
    """Aplica `fn(e)` numa transação. Devolve '' ou o motivo de não poder."""
    with db.transacao() as con:
        e = _ler(con)
        if _travada(e):
            return "A criação já começou: a escala não muda mais."
        erro = fn(e)
        if erro:
            return erro
        _recalcular(e)
        _gravar(con, e)
    return ""


def definir(local: str, dia: str, campo: str, valor: str) -> str:
    def fn(e):
        if campo != "tecnico" or local not in e["escala"]:
            return "Campo inválido."
        if dia not in e["escala"][local]:
            return "Dia fora da escala."
        e["escala"][local][dia][campo] = valor
    return _mudar(fn)


def remover_dia(iso: str) -> str:
    def fn(e):
        if iso not in e["dias"]:
            return "Dia fora da escala."
        if datetime.date.fromisoformat(iso).weekday() >= 5:
            return "Sábado e domingo são fixos."
        e["dias"].remove(iso)
        e.setdefault("removidos", []).append(iso)
        for c, *_ in LOCAIS:
            e["escala"][c].pop(iso, None)
    return _mudar(fn)


def definir_supervisor(matricula: str) -> str:
    salvar_supervisor(matricula)
    return _mudar(lambda e: None)


def nova_escala() -> None:
    """Depois de criada (ou para recomeçar): próximo fim de semana, vazia."""
    with db.transacao() as con:
        e = _ler(con)
        if e["sentinela"].get("fase") == CRIANDO:
            return
        _gravar(con, _nova(proximo_fim_de_semana(datetime.date.today()), e["sentinela"]))


# --------------------------------------------------------------------------- #
# Sentinela
# --------------------------------------------------------------------------- #

def ligar(matricula: str) -> None:
    with db.transacao() as con:
        e = _ler(con)
        e["sentinela"].update({"ligado": True, "matricula": matricula})
        if not _travada(e):
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
        e["sentinela"].update({"hora_fixa": {"hora": f"{h:02d}:{m:02d}"},
                               "avisou_incompleto": False})
        _gravar(con, e)
    return ""


def tentar_de_novo() -> None:
    """Depois de erro: cria o que faltou (o checkpoint pula as já criadas)."""
    with db.transacao() as con:
        e = _ler(con)
        if e["sentinela"].get("fase") == ERRO:
            e["sentinela"]["fase"] = ""
            _gravar(con, e)


def _pegar_vez(agora: float) -> "tuple[str, dict] | None":
    """('criar' | 'avisar', estado) ou None. Em transação: dois backends
    (hot-reload) nunca criam juntos."""
    with db.transacao() as con:
        e = _ler(con)
        s = e["sentinela"]
        if not s.get("ligado") or _travada(e):
            return None
        if agora < momento_fixo(e).timestamp():
            return None
        # Passou da hora: completa inicia já; incompleta avisa uma vez e
        # inicia assim que completar.
        if not faltando(e):
            s.update({"fase": CRIANDO, "resumo": "Criando as Requisições..."})
            _gravar(con, e)
            return "criar", e
        if not s.get("avisou_incompleto"):
            s["avisou_incompleto"] = True
            _gravar(con, e)
            return "avisar", e
    return None


def _concluir(fase: str, resumo: str) -> None:
    with db.transacao() as con:
        e = _ler(con)
        e["sentinela"].update({"fase": fase, "resumo": resumo,
                               "quando": datetime.datetime.now().strftime("%d/%m %H:%M")})
        _gravar(con, e)


def _telegram(matricula: str, texto: str) -> None:
    from services.agente import agendados
    r = db.consultar("SELECT chat_id FROM bot_credenciais WHERE matricula = ? LIMIT 1",
                     (matricula,))
    if r and r[0]["chat_id"] is not None:
        agendados._mandar_telegram(r[0]["chat_id"], texto)


def _criar(e: dict) -> None:
    from services.agente.ferramentas import requisicao
    from services.agente.sessao import Sessao
    from services.dados import credenciais

    dono = e["sentinela"].get("matricula", "")
    matricula, senha = credenciais.carregar()
    if matricula != dono or not senha:
        _concluir(ERRO, "A credencial do app não é a de quem ligou o Sentinela.")
        return
    acao = requisicao._prep_requisicoes({"requisicoes": requisicoes(e)})
    if isinstance(acao, str):
        _concluir(ERRO, acao)
        return
    sessao = Sessao(matricula, senha, lambda m, t="info": log.info("%s", m))
    try:
        res = requisicao._exec_requisicoes(acao.args, sessao)
        fase, texto = (CONCLUIDO if res.ok else ERRO), res.texto
    except Exception as ex:
        fase, texto = ERRO, f"❌ {ex or type(ex).__name__}"
    finally:
        sessao.fechar()
    _concluir(fase, texto)
    dias = ", ".join(rotulo_dia(d) for d in datas(e))
    _telegram(dono, f"🛡️ Plantões Judiciários ({dias})\n\n{texto}")


def _avisar_incompleto(e: dict) -> None:
    falta = faltando(e)
    texto = ("Chegou o horário de criar os plantões, mas a escala está incompleta. "
             "Falta: " + ", ".join(falta) + ". Inicia assim que completar.")
    with db.transacao() as con:
        e2 = _ler(con)
        e2["sentinela"]["resumo"] = "⚠️ " + texto
        _gravar(con, e2)
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
                if e["sentinela"].get("fase") == CRIANDO:
                    e["sentinela"].update({"fase": ERRO, "resumo":
                                           "O app fechou no meio da criação. Confira e tente de novo."})
                    _gravar(con, e)
        except Exception:
            log.exception("Plantões: falha ao limpar o estado")
        while True:
            try:
                vez = _pegar_vez(time.time())
                if vez and vez[0] == "criar":
                    _criar(vez[1])
                elif vez:
                    _avisar_incompleto(vez[1])
            except Exception:
                log.exception("Falha no Sentinela dos plantões")
            time.sleep(_CHECAGEM_S)

    threading.Thread(target=laco, daemon=True, name="plantoes").start()
