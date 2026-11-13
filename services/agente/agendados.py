"""
services/agente/agendados.py — Início agendado do Atendimento Programado (05/11).

Quando o Assistente programa um chamado, o início também vai para o banco (tabela
`tarefas`, tipo 'iniciar_programado'). A tela Iniciar Atendimento usa o mesmo banco.
Um vigia em cada processo confere a cada 20 s o que venceu e inicia. Por estar no
banco, o agendamento sobrevive a reiniciar.

QUEM RODA (decisão do usuário, 06/11): o app ou o bot, o que estiver aberto, inicia
qualquer tarefa. Antes cada um só rodava as próprias, e com a tolerância curta um
chamado se perdia com o outro aberto. O login é sempre o de quem pediu: `chat_id`
preenchido é credencial do bot, vazio é a do app. A SENHA não vai para o banco: é
lida do cofre na hora. Só vale com os dois na mesma máquina e conta do Windows, que
é onde o banco e o cofre são os mesmos.

ATRASO (decisão do usuário, 05/11): com o processo fechado na hora marcada, inicia
ao voltar só dentro da tolerância. Passou dela, não faz nada e registra o motivo.

NA HORA DE INICIAR, o histórico é conferido: se a última ação de relógio não for
mais 'Atendimento Programado' (o técnico já iniciou, resolveu ou pausou de outro
jeito), não inicia. 'Atendimento Iniciado' poderia retomar uma pausa de outro tipo.

SEM NOVA TENTATIVA: se falhar no meio, o Assyst pode ter salvo. Vira erro e o
técnico confere. Pelo mesmo motivo, 'executando' parado há mais de 15 min (processo
caiu no meio) vira erro em vez de rodar de novo.
"""

import asyncio
import datetime
import json
import logging
import threading
import time
import uuid

from services.agente.sessao import ErroSessao, Sessao
from services.dados import db

TIPO = "iniciar_programado"
PENDENTE, EXECUTANDO = "pendente", "executando"
CONCLUIDO, ERRO, CANCELADO = "concluido", "erro", "cancelado"
# 13/11: Programado que o sentinela achou sem dia/hora no texto. Fica na tabela
# para o técnico ver; o vigia nunca roda (sem executar_em).
AGUARDANDO = "aguardando"

_INTERVALO_S = 20
_ATRASO_MIN = 5   # acima disto, o aviso diz a hora que estava marcada
_TOLERANCIA_MIN = 6   # a partir disto, não inicia mais

log = logging.getLogger("agendados")


def data_do_inicio(dia: str, hora: str, agora: "datetime.datetime | None" = None) -> datetime.datetime:
    """'dd/mm' + 'hh:mm' -> data. Sem ano: 02/01 pedido em dezembro é o ano que vem.
    Levanta ValueError se a data não existir ou já tiver passado."""
    agora = agora or datetime.datetime.now()
    d, m = map(int, dia.split("/"))
    h, mi = map(int, hora.split(":"))
    try:
        alvo = datetime.datetime(agora.year, m, d, h, mi)
        if (agora - alvo).days > 180:
            alvo = alvo.replace(year=agora.year + 1)
    except ValueError:
        raise ValueError(f"A data {dia} não existe.") from None
    if alvo <= agora:
        raise ValueError(f"{dia} às {hora} já passou. Pergunte ao técnico o dia e a hora.")
    return alvo


def agendar(numero: str, quando: datetime.datetime, matricula: str, chat_id=None) -> None:
    """Grava o início. Programar de novo o mesmo chamado substitui o anterior."""
    numero = numero.strip().upper()
    with db.transacao() as con:
        con.execute(
            "DELETE FROM tarefas WHERE tipo = ? AND status = ? "
            "AND json_extract(dados, '$.chamado') = ?", (TIPO, AGUARDANDO, numero))
        con.execute(
            "UPDATE tarefas SET status = ?, detalhe = 'Programado de novo.', "
            "atualizado_em = datetime('now', 'localtime') "
            "WHERE tipo = ? AND status = ? AND json_extract(dados, '$.chamado') = ?",
            (CANCELADO, TIPO, PENDENTE, numero))
        con.execute(
            "INSERT INTO tarefas (id, tipo, chat_id, quem, dados, executar_em, "
            "executar_em_label, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, TIPO, chat_id, matricula,
             json.dumps({"chamado": numero}, ensure_ascii=False),
             quando.timestamp(), quando.strftime("%d/%m/%Y %H:%M"), PENDENTE))


def aguardar(numero: str, matricula: str, detalhe: str) -> bool:
    """Põe na tabela como Aguardando (não há hora para iniciar: sem data ou
    horário já passado). Já estando lá, só atualiza o detalhe; pendente não é
    mexido. True = entrou agora."""
    numero = numero.strip().upper()
    with db.transacao() as con:
        if con.execute(
                "SELECT 1 FROM tarefas WHERE tipo = ? AND status = ? "
                "AND json_extract(dados, '$.chamado') = ?",
                (TIPO, PENDENTE, numero)).fetchone():
            return False
        if con.execute(
                "UPDATE tarefas SET detalhe = ?, atualizado_em = datetime('now', 'localtime') "
                "WHERE tipo = ? AND status = ? AND json_extract(dados, '$.chamado') = ?",
                (detalhe, TIPO, AGUARDANDO, numero)).rowcount:
            return False
        con.execute(
            "INSERT INTO tarefas (id, tipo, quem, dados, executar_em_label, status, detalhe) "
            "VALUES (?, ?, ?, ?, '', ?, ?)",
            (uuid.uuid4().hex, TIPO, matricula,
             json.dumps({"chamado": numero}, ensure_ascii=False), AGUARDANDO, detalhe))
    return True


def limpar_aguardando(matricula: str, manter: set[str]) -> None:
    """Tira os Aguardando que não estão mais em `manter` (o chamado foi
    iniciado, saiu da fila ou ganhou dia/hora)."""
    with db.transacao() as con:
        for r in con.execute(
                "SELECT id, dados FROM tarefas WHERE tipo = ? AND quem = ? AND status = ?",
                (TIPO, matricula, AGUARDANDO)).fetchall():
            if json.loads(r["dados"])["chamado"] not in manter:
                con.execute("DELETE FROM tarefas WHERE id = ?", (r["id"],))


def _dict(r) -> dict:
    return {"id": r["id"], "chamado": json.loads(r["dados"])["chamado"], "chat_id": r["chat_id"],
            "quem": r["quem"], "quando": r["executar_em_label"], "executar_em": r["executar_em"],
            "status": r["status"], "detalhe": r["detalhe"]}


def listar(matricula: str) -> tuple[list[dict], list[dict]]:
    """(pendentes, os 10 últimos já encerrados) desta matrícula."""
    pendentes = db.consultar(
        "SELECT * FROM tarefas WHERE tipo = ? AND quem = ? AND status IN (?, ?, ?) "
        "ORDER BY executar_em IS NULL, executar_em",
        (TIPO, matricula, PENDENTE, EXECUTANDO, AGUARDANDO))
    encerrados = db.consultar(
        "SELECT * FROM tarefas WHERE tipo = ? AND quem = ? AND status NOT IN (?, ?, ?) "
        "ORDER BY atualizado_em DESC LIMIT 10",
        (TIPO, matricula, PENDENTE, EXECUTANDO, AGUARDANDO))
    return [_dict(r) for r in pendentes], [_dict(r) for r in encerrados]


def cancelar(numeros: list[str], matricula: str) -> list[str]:
    """Cancela os pendentes desta matrícula. Devolve os que estavam mesmo agendados."""
    cancelados = []
    with db.transacao() as con:
        for numero in (n.strip().upper() for n in numeros):
            feitos = con.execute(
                "UPDATE tarefas SET status = ?, detalhe = 'Cancelado pelo técnico.', "
                "atualizado_em = datetime('now', 'localtime') "
                "WHERE tipo = ? AND quem = ? AND status = ? AND json_extract(dados, '$.chamado') = ?",
                (CANCELADO, TIPO, matricula, PENDENTE, numero)).rowcount
            if feitos:
                cancelados.append(numero)
    return cancelados


def excluir(id_tarefa: str, matricula: str) -> bool:
    """O X da tela (13/11): apaga a linha da agenda. Só isso: agendar de novo
    (técnico, Assistente ou sentinela) cria outra. Em execução não apaga."""
    with db.transacao() as con:
        return bool(con.execute(
            "DELETE FROM tarefas WHERE id = ? AND quem = ? AND status != ?",
            (id_tarefa, matricula, EXECUTANDO)).rowcount)


def _pegar_vencidas(agora: float) -> list[dict]:
    """Marca como executando e devolve, tudo numa transação: dois processos (ou
    dois backends do hot-reload) nunca pegam a mesma tarefa."""
    with db.transacao() as con:
        con.execute(
            "UPDATE tarefas SET status = ?, detalhe = 'Interrompido no meio: confira no Assyst.', "
            "atualizado_em = datetime('now', 'localtime') "
            "WHERE tipo = ? AND status = ? "
            "AND atualizado_em < datetime('now', 'localtime', '-15 minutes')",
            (ERRO, TIPO, EXECUTANDO))
        linhas = con.execute(
            "SELECT * FROM tarefas WHERE tipo = ? AND status = ? "
            "AND executar_em <= ? ORDER BY executar_em",
            (TIPO, PENDENTE, agora)).fetchall()
        for r in linhas:
            con.execute(
                "UPDATE tarefas SET status = ?, atualizado_em = datetime('now', 'localtime') "
                "WHERE id = ?", (EXECUTANDO, r["id"]))
    return [_dict(r) for r in linhas]


def _encerrar(id_tarefa: str, status: str, detalhe: str) -> None:
    with db.transacao() as con:
        con.execute(
            "UPDATE tarefas SET status = ?, detalhe = ?, "
            "atualizado_em = datetime('now', 'localtime') WHERE id = ?",
            (status, detalhe, id_tarefa))


def _registrar(m, tipo="info") -> None:
    log.info("%s", m)


def _iniciar_um(s: Sessao, numero: str) -> tuple[str, str]:
    from services.agente.ferramentas.verificacoes import _pausa_atual
    from services.agente.ficha import esquecer
    from services.fluxos.flow_atendimento_pw import iniciar_atendimento
    from services.fluxos.flow_sla_pw import extrair_historico_chamado

    page = s.pagina()
    historico = extrair_historico_chamado(page, numero, s.log)
    if not historico:
        return ERRO, "Não consegui ler o histórico: o atendimento não foi iniciado."
    pausa = _pausa_atual(historico)
    if not pausa or pausa[0] != "Atendimento Programado":
        return CANCELADO, "Não está mais em Atendimento Programado: o atendimento não foi iniciado."
    ok = iniciar_atendimento(page, s.log, numero)
    esquecer(numero)
    if ok:
        return CONCLUIDO, "Atendimento iniciado."
    return ERRO, "A ação 'Atendimento Iniciado' falhou: confira no Assyst."


def _credencial(t: dict) -> tuple[str, str]:
    if t["chat_id"] is not None:
        from bot.services import credencial_servico
        return credencial_servico.carregar_de(t["chat_id"])
    from services.dados import credenciais
    return credenciais.carregar()


def _mandar_telegram(chat_id, texto: str) -> None:
    """Em thread própria: asyncio.run não roda na thread do Playwright sync. Quem
    manda pode ser o app, então não dá para usar o bot que está no ar."""
    from telegram import Bot
    from bot.services import credencial_servico

    token = credencial_servico.carregar_token()
    if not token:
        log.warning("Sem o token do bot: aviso não enviado.")
        return

    async def enviar():
        async with Bot(token) as bot:
            await bot.send_message(chat_id, texto)

    def rodar():
        try:
            asyncio.run(enviar())
        except Exception as e:
            log.warning("Aviso não enviado ao Telegram: %s", type(e).__name__)

    envio = threading.Thread(target=rodar, daemon=True)
    envio.start()
    envio.join(30)


def _avisar(t: dict, status: str, detalhe: str) -> None:
    log.info("Início agendado de %s: %s", t["chamado"], status)
    if t["chat_id"] is not None:
        icone = "✅" if status == CONCLUIDO else "❌"
        try:
            _mandar_telegram(t["chat_id"], f"{icone} Início agendado do {t['chamado']}: {detalhe}")
        except Exception:
            log.exception("Não consegui avisar sobre o chamado %s", t["chamado"])


def _rodar_grupo(tarefas: list[dict]) -> None:
    """Tarefas da mesma pessoa: um login só."""
    matricula, senha = _credencial(tarefas[0])
    sessao = None
    if matricula == tarefas[0]["quem"] and senha:
        sessao = Sessao(matricula, senha, _registrar)
    erro_geral = "" if sessao else "A credencial desta matrícula não está cadastrada: o atendimento não foi iniciado."
    try:
        for t in tarefas:
            if erro_geral:
                status, detalhe = ERRO, erro_geral
            else:
                try:
                    status, detalhe = _iniciar_um(sessao, t["chamado"])
                except ErroSessao as e:
                    erro_geral = f"{e} O atendimento não foi iniciado."
                    status, detalhe = ERRO, erro_geral
                except Exception as e:
                    status, detalhe = ERRO, f"{e} Confira no Assyst."
            if status == CONCLUIDO and time.time() - t["executar_em"] > _ATRASO_MIN * 60:
                detalhe += f" Estava marcado para {t['quando']}."
            _encerrar(t["id"], status, detalhe)
            _avisar(t, status, detalhe)
    finally:
        if sessao:
            sessao.fechar()


def rodar_vencidas() -> int:
    tarefas = _pegar_vencidas(time.time())
    grupos: dict[tuple, list[dict]] = {}
    for t in tarefas:
        if time.time() - t["executar_em"] >= _TOLERANCIA_MIN * 60:
            detalhe = (f"Passou mais de {_TOLERANCIA_MIN} min da hora marcada "
                       f"({t['quando']}): o atendimento não foi iniciado.")
            _encerrar(t["id"], CANCELADO, detalhe)
            _avisar(t, CANCELADO, detalhe)
        else:
            grupos.setdefault((t["chat_id"], t["quem"]), []).append(t)
    for grupo in grupos.values():
        _rodar_grupo(grupo)
    return len(tarefas)


_vigia_ligado = False
_vigia_lock = threading.Lock()


def iniciar_vigia() -> None:
    """Liga o vigia deste processo, uma vez só. Thread própria: o Playwright sync
    se prende à thread que o abriu."""
    global _vigia_ligado
    with _vigia_lock:
        if _vigia_ligado:
            return
        _vigia_ligado = True

    def laco():
        while True:
            try:
                rodar_vencidas()
            except Exception:
                log.exception("Falha no vigia dos inícios agendados")
            time.sleep(_INTERVALO_S)

    threading.Thread(target=laco, daemon=True, name="vigia-agendados").start()
