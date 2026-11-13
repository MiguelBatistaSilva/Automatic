"""
services/agente/sentinela.py — Modo Sentinela da página Iniciar Atendimento (13/11).

Ligado por um técnico ("Sentry Mode"), varre a fila 2N CATI FCB a cada 5 horas:
cada chamado cuja última ação de relógio é 'Atendimento Programado' tem o dia e
a hora lidos do TEXTO dessa ação (padrão do flow_programar_pw: "...programado
para o dia dd/mm às hh:mm.") e vai para a agenda dos inícios agendados
(services/agente/agendados.py), que inicia na hora. Nada é iniciado aqui.

Decisões dele (13/11):
  - fila da equipe (2N CATI FCB), não a Minha Fila;
  - horário que já passou: NÃO inicia, só avisa;
  - Programado fora do padrão (sem dia/hora no texto): só avisa;
  - roda na máquina de quem ligou, com o login dele (credencial do app);
  - avisos na página e, se ele usa o bot, um resumo no Telegram dele. O mesmo
    aviso do mesmo chamado não é repetido a cada varredura.

Só reaproveita: ler_fila (flow_minhafila_pw), extrair_historico_chamado
(flow_sla_pw), _pausa_atual (verificações do Assistente) e a agenda. Nenhum
arquivo de fluxo foi mexido.

Estado em app_config['sentinela_iniciar'] (JSON), para sobreviver a reiniciar.
Quem roda é o backend do app (lifespan em automatic_app.py), não a tela.
"""

import datetime
import json
import logging
import re
import threading
import time

from services.dados import db

FILA = "2N CATI FCB"
INTERVALO_H = 5
_CHAVE = "sentinela_iniciar"
_CHECAGEM_S = 60
_PROGRAMADO = "Atendimento Programado"

log = logging.getLogger("sentinela")

# "programado para o dia 14/11 às 08:00" / "dia 14/11/2026 às 8h" / "as 14h30"
_RE_DIA_HORA = re.compile(
    r"programad[oa]\s+para\s+(?:o\s+)?dia\s+(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?"
    r"\s*,?\s*(?:às|as|à|a)\s+(\d{1,2})\s*(?:[:h]\s*(\d{2})?)",
    re.I)


# --------------------------------------------------------------------------- #
# Estado
# --------------------------------------------------------------------------- #

def estado() -> dict:
    r = db.consultar("SELECT valor FROM app_config WHERE chave = ?", (_CHAVE,))
    try:
        return json.loads(r[0]["valor"]) if r else {}
    except (ValueError, KeyError):
        return {}


def _ler(con) -> dict:
    r = con.execute("SELECT valor FROM app_config WHERE chave = ?", (_CHAVE,)).fetchone()
    try:
        return json.loads(r["valor"]) if r else {}
    except (ValueError, KeyError):
        return {}


def _gravar(con, e: dict) -> None:
    con.execute("INSERT OR REPLACE INTO app_config VALUES (?, ?)",
                (_CHAVE, json.dumps(e, ensure_ascii=False)))


def ligar(matricula: str) -> None:
    """Liga e marca a 1ª varredura para já."""
    with db.transacao() as con:
        e = _ler(con)
        e.update({"ligado": True, "matricula": matricula, "fila": FILA,
                  "proxima": time.time(), "rodando": False})
        _gravar(con, e)


def desligar() -> None:
    with db.transacao() as con:
        e = _ler(con)
        e["ligado"] = False
        _gravar(con, e)


def _pegar_vez() -> dict | None:
    """Marca a próxima varredura e devolve o estado, numa transação: dois
    backends (hot-reload) nunca varrem juntos."""
    with db.transacao() as con:
        e = _ler(con)
        if not e.get("ligado") or time.time() < e.get("proxima", 0):
            return None
        e["proxima"] = time.time() + INTERVALO_H * 3600
        e["rodando"] = True
        _gravar(con, e)
        return e


def _concluir(resumo: dict, avisados: dict) -> None:
    with db.transacao() as con:
        e = _ler(con)
        e.update({"rodando": False, "ultima": resumo["quando"], "resumo": resumo,
                  "avisados": avisados})
        _gravar(con, e)


# --------------------------------------------------------------------------- #
# Leitura do dia e hora
# --------------------------------------------------------------------------- #

def dia_hora_do_texto(texto: str, registrado_em: datetime.datetime) -> datetime.datetime | None:
    """Dia e hora do texto da ação. Sem ano: a 1ª ocorrência a partir do dia em
    que foi programado. None = não está no padrão."""
    m = _RE_DIA_HORA.search(re.sub(r"\s+", " ", texto or ""))
    if not m:
        return None
    d, mes, ano, h, mi = m[1], m[2], m[3], m[4], m[5] or "0"
    try:
        if ano:
            ano = int(ano) + (2000 if len(ano) == 2 else 0)
            return datetime.datetime(ano, int(mes), int(d), int(h), int(mi))
        alvo = datetime.datetime(registrado_em.year, int(mes), int(d), int(h), int(mi))
        if alvo.date() < registrado_em.date() - datetime.timedelta(days=1):
            alvo = alvo.replace(year=alvo.year + 1)
        return alvo
    except ValueError:
        return None


def _ultimo_programado(historico: list[dict]) -> dict | None:
    """A ação 'Atendimento Programado' mais recente (o histórico vem do mais
    novo para o mais antigo)."""
    return next((h for h in historico if h.get("tipo") == _PROGRAMADO), None)


def _quando(dt: datetime.datetime) -> str:
    return dt.strftime("%d/%m %H:%M")


# --------------------------------------------------------------------------- #
# Varredura
# --------------------------------------------------------------------------- #

def varrer(page, matricula: str, registrar=None) -> dict:
    """Lê a fila e agenda os Programados. Devolve o resumo:
    {quando, fila, total, programados, agendados[], ja_agendados[], atrasados[],
     sem_data[], erros[]}. `registrar(msg)` recebe o andamento."""
    from services.agente import agendados
    from services.agente.ferramentas.verificacoes import _pausa_atual
    from services.fluxos.flow_minhafila_pw import ler_fila
    from services.fluxos.flow_sla_pw import extrair_historico_chamado

    registrar = registrar or (lambda m: log.info("%s", m))
    flog = lambda m, t="info": None   # o log dos fluxos é detalhado demais aqui
    agora = datetime.datetime.now()
    res = {"quando": agora.strftime("%d/%m %H:%M"), "fila": FILA, "total": 0,
           "programados": 0, "agendados": [], "ja_agendados": [], "atrasados": [],
           "sem_data": [], "erros": []}

    fila = ler_fila(page, flog, FILA)
    if fila is None:
        res["erros"].append("não consegui abrir a fila")
        return res
    refs = [c["referencia"] for c in fila if c.get("referencia")]
    res["total"] = len(refs)
    registrar(f"Fila {FILA}: {len(refs)} chamados.")

    pendentes = {t["chamado"]: t for t in agendados.listar(matricula)[0]
                 if t["status"] == agendados.PENDENTE}
    for n, ref in enumerate(refs, 1):
        try:
            historico = extrair_historico_chamado(page, ref, flog) or []
        except Exception as e:
            res["erros"].append(f"{ref}: {e}")
            continue
        pausa = _pausa_atual(historico)
        if not pausa or pausa[0] != _PROGRAMADO:
            continue
        res["programados"] += 1
        acao = _ultimo_programado(historico) or {}
        try:
            registrado = datetime.datetime.strptime(acao.get("data", ""), "%d/%m/%y %H:%M")
        except ValueError:
            registrado = agora
        alvo = dia_hora_do_texto(acao.get("descricao", ""), registrado)
        if alvo is None:
            res["sem_data"].append({"chamado": ref})
            # 13/11: sem data e atrasado vão para a tabela como Aguardando.
            agendados.aguardar(ref, matricula, "Sem data/hora")
            registrar(f"{ref}: Programado sem dia e hora no texto.")
        elif alvo <= agora:
            res["atrasados"].append({"chamado": ref, "quando": _quando(alvo)})
            agendados.aguardar(ref, matricula, f"Horário já passou (era {_quando(alvo)})")
            registrar(f"{ref}: estava marcado para {_quando(alvo)}, não iniciei.")
        elif ref in pendentes and abs(pendentes[ref]["executar_em"] - alvo.timestamp()) < 60:
            res["ja_agendados"].append({"chamado": ref, "quando": _quando(alvo)})
        else:
            agendados.agendar(ref, alvo, matricula)
            res["agendados"].append({"chamado": ref, "quando": _quando(alvo),
                                     "mudou": ref in pendentes})
            registrar(f"{ref}: agendado para {_quando(alvo)}.")
    # Aguardando que não está mais sem data (iniciado, saiu da fila, ganhou
    # dia/hora) sai da tabela. Só com a fila lida inteira e sem erro.
    if not res["erros"]:
        agendados.limpar_aguardando(
            matricula, {a["chamado"] for a in res["sem_data"] + res["atrasados"]})
    return res


def _novos_avisos(res: dict, avisados: dict) -> tuple[dict, dict]:
    """Só o que ainda não foi avisado. Devolve (o que avisar, avisados novo).
    Chamado que saiu dos avisos (iniciado, reprogramado) é esquecido."""
    atual = {}
    for a in res["atrasados"]:
        atual[a["chamado"]] = f"atrasado|{a['quando']}"
    for a in res["sem_data"]:
        atual[a["chamado"]] = "sem_data"
    novos = {c: k for c, k in atual.items() if avisados.get(c) != k}
    avisar = {
        "agendados": res["agendados"],
        "atrasados": [a for a in res["atrasados"] if a["chamado"] in novos],
        "sem_data": [a for a in res["sem_data"] if a["chamado"] in novos],
        "erros": res["erros"],
    }
    return avisar, atual


def mensagem(res: dict, avisar: dict, proxima: str) -> str:
    """O resumo do Telegram. '' = nada novo para dizer."""
    if not any(avisar.values()):
        return ""
    linhas = [f"🛡️ Sentinela · {res['fila']} · {res['quando']}"]
    if avisar["agendados"]:
        linhas.append("")
        linhas.append("📅 Agendados para iniciar:")
        linhas += [f"• {a['chamado']} — {a['quando']}" + (" (horário mudou)" if a.get("mudou") else "")
                   for a in avisar["agendados"]]
    if avisar["atrasados"]:
        linhas.append("")
        linhas.append("⚠️ Horário já passou, não iniciei:")
        linhas += [f"• {a['chamado']} — era {a['quando']}" for a in avisar["atrasados"]]
    if avisar["sem_data"]:
        linhas.append("")
        linhas.append("⚠️ Programado sem dia e hora no texto, inicie na mão:")
        linhas += [f"• {a['chamado']}" for a in avisar["sem_data"]]
    if avisar["erros"]:
        linhas.append("")
        linhas.append("❌ Não consegui ler:")
        linhas += [f"• {e}" for e in avisar["erros"]]
    linhas.append("")
    linhas.append(f"Próxima varredura: {proxima}")
    return "\n".join(linhas)


def _chat_id_de(matricula: str):
    r = db.consultar("SELECT chat_id FROM bot_credenciais WHERE matricula = ? LIMIT 1",
                     (matricula,))
    return r[0]["chat_id"] if r else None


def _rodar_vez(e: dict) -> None:
    from services.agente import agendados
    from services.agente.sessao import Sessao
    from services.dados import credenciais

    matricula, senha = credenciais.carregar()
    proxima = datetime.datetime.fromtimestamp(e["proxima"]).strftime("%d/%m %H:%M")
    if matricula != e.get("matricula") or not senha:
        res = {"quando": datetime.datetime.now().strftime("%d/%m %H:%M"), "fila": FILA,
               "total": 0, "programados": 0, "agendados": [], "ja_agendados": [],
               "atrasados": [], "sem_data": [],
               "erros": ["a credencial do app não é a de quem ligou o sentinela"]}
    else:
        sessao = Sessao(matricula, senha, lambda m, t="info": None)
        try:
            res = varrer(sessao.pagina(), matricula)
        except Exception as ex:
            res = {"quando": datetime.datetime.now().strftime("%d/%m %H:%M"), "fila": FILA,
                   "total": 0, "programados": 0, "agendados": [], "ja_agendados": [],
                   "atrasados": [], "sem_data": [], "erros": [str(ex) or type(ex).__name__]}
        finally:
            sessao.fechar()

    avisar, avisados = _novos_avisos(res, e.get("avisados") or {})
    res["proxima"] = proxima
    _concluir(res, avisados)
    texto = mensagem(res, avisar, proxima)
    chat_id = _chat_id_de(e.get("matricula", ""))
    if texto and chat_id is not None:
        agendados._mandar_telegram(chat_id, texto)


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
        # Varredura que caiu no meio (app fechado) não fica 'rodando' para sempre.
        try:
            with db.transacao() as con:
                e = _ler(con)
                if e.get("rodando"):
                    e["rodando"] = False
                    _gravar(con, e)
        except Exception:
            log.exception("Sentinela: falha ao limpar o estado")
        while True:
            try:
                e = _pegar_vez()
                if e:
                    _rodar_vez(e)
            except Exception:
                log.exception("Falha na varredura do sentinela")
            time.sleep(_CHECAGEM_S)

    threading.Thread(target=laco, daemon=True, name="sentinela").start()
