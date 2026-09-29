"""
bot/agenda.py — os agendamentos do Iniciar Atendimento, gravados em disco.

POR QUE EM DISCO: um agendamento vive entre o pedido e a hora marcada, as vezes
por horas. Se ficasse so na memoria, reiniciar o bot (atualizacao do Windows,
queda de energia, um Ctrl+C distraido) apagaria tudo em silencio — e a pessoa so
descobriria as 14:30, quando nada acontecesse.

NAO CONFUNDIR COM O CHECKPOINT dos outros fluxos. O checkpoint registra o que JA
FOI FEITO, para poder retomar de onde parou. A agenda registra o que AINDA VAI
SER FEITO. Sao direcoes opostas no tempo.

ONDE MORA: tabela `tarefas` do banco (services/db.py), tipo 'atendimento',
desde 2026-09-28 — antes era data/agenda_bot.json. A tabela ja tem o formato
da futura fila de tarefas de todos os fluxos; a interface deste modulo (Item,
adicionar, listar, separar_vencidos...) nao mudou. O RLock que existia aqui
saiu: cada operacao e uma transacao BEGIN IMMEDIATE, que serializa inclusive
entre processos (o lock so valia dentro de um).
"""
import json
import time
from dataclasses import dataclass

from services import db

TIPO = "atendimento"

PENDENTE = "pendente"
EXECUTANDO = "executando"
CONCLUIDO = "concluido"
ERRO = "erro"
PERDIDO = "perdido"
CANCELADO = "cancelado"
INDEFINIDO = "indefinido"

# Status que ainda ocupam a agenda (aparecem no /agenda, podem ser cancelados).
ABERTOS = (PENDENTE, EXECUTANDO)


@dataclass
class Item:
    id: str
    chat_id: int
    quem: str            # nome de quem agendou, para o log e o aviso
    chamado: str
    quando_ts: float
    quando_label: str
    status: str = PENDENTE
    detalhe: str = ""


def _item(r) -> Item:
    return Item(
        id=r["id"], chat_id=r["chat_id"], quem=r["quem"],
        chamado=json.loads(r["dados"]).get("chamado", ""),
        quando_ts=r["executar_em"], quando_label=r["executar_em_label"],
        status=r["status"], detalhe=r["detalhe"],
    )


def _marcar(con, item_id, status, detalhe=None) -> None:
    if detalhe is None:
        con.execute(
            "UPDATE tarefas SET status = ?, "
            "atualizado_em = datetime('now', 'localtime') WHERE id = ?",
            (status, item_id))
    else:
        con.execute(
            "UPDATE tarefas SET status = ?, detalhe = ?, "
            "atualizado_em = datetime('now', 'localtime') WHERE id = ?",
            (status, detalhe, item_id))


def carregar_ao_subir() -> list:
    """Sanea a agenda na subida do bot. Devolve os itens que ficaram em duvida.

    Item marcado EXECUTANDO quer dizer que o bot caiu no meio de uma execucao:
    nao da para saber se a acao chegou a ser salva no Assyst. Marcar como erro
    seria mentira, marcar como concluido tambem — vira INDEFINIDO, e a pessoa e
    avisada para conferir na mao.
    """
    with db.transacao() as con:
        duvidosos = [_item(r) for r in con.execute(
            "SELECT * FROM tarefas WHERE tipo = ? AND status = ?",
            (TIPO, EXECUTANDO)).fetchall()]
        for i in duvidosos:
            i.status = INDEFINIDO
            i.detalhe = "O bot caiu durante a execucao"
            _marcar(con, i.id, i.status, i.detalhe)
        return duvidosos


def listar(chat_id=None, apenas_abertos=False) -> list:
    itens = [_item(r) for r in db.consultar(
        "SELECT * FROM tarefas WHERE tipo = ? ORDER BY executar_em", (TIPO,))]
    if chat_id is not None:
        itens = [i for i in itens if i.chat_id == chat_id]
    if apenas_abertos:
        itens = [i for i in itens if i.status in ABERTOS]
    return itens


def adicionar(chat_id, quem, chamado, quando_ts, quando_label) -> Item:
    item = Item(
        id=str(int(time.time() * 1000)),
        chat_id=chat_id,
        quem=quem,
        chamado=chamado,
        quando_ts=quando_ts,
        quando_label=quando_label,
    )
    with db.transacao() as con:
        con.execute(
            "INSERT INTO tarefas (id, tipo, chat_id, quem, dados, executar_em, "
            "executar_em_label, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (item.id, TIPO, chat_id, quem,
             json.dumps({"chamado": chamado}, ensure_ascii=False),
             quando_ts, quando_label, item.status))
    return item


def cancelar(item_id, chat_id) -> Item | None:
    """Cancela um item. So o dono cancela — e so enquanto ainda esta PENDENTE."""
    with db.transacao() as con:
        r = con.execute(
            "SELECT * FROM tarefas WHERE id = ? AND tipo = ? AND chat_id = ? "
            "AND status = ?", (item_id, TIPO, chat_id, PENDENTE)).fetchone()
        if r is None:
            return None
        _marcar(con, item_id, CANCELADO)
        i = _item(r)
        i.status = CANCELADO
        return i


def separar_vencidos(agora, tolerancia_s) -> tuple:
    """Devolve (para_rodar, perdidos) e ja marca os dois no banco.

    Perdido e agendamento cujo horario passou ha mais que a tolerancia — o
    chamado precisa iniciar NA hora marcada, entao rodar atrasado seria pior do
    que nao rodar. A tolerancia existe so por causa do intervalo do laco.
    """
    with db.transacao() as con:
        rodar, perdidos = [], []
        for r in con.execute(
                "SELECT * FROM tarefas WHERE tipo = ? AND status = ? "
                "AND executar_em <= ?", (TIPO, PENDENTE, agora)).fetchall():
            i = _item(r)
            if agora - i.quando_ts <= tolerancia_s:
                i.status = EXECUTANDO
                rodar.append(i)
            else:
                i.status = PERDIDO
                i.detalhe = "O bot nao estava no ar na hora marcada"
                perdidos.append(i)
            _marcar(con, i.id, i.status, i.detalhe)
        return rodar, perdidos


def concluir(item_id, ok, detalhe="") -> None:
    with db.transacao() as con:
        _marcar(con, item_id, CONCLUIDO if ok else ERRO, detalhe)
