"""
bot/usuarios.py — quem pode falar com o bot (whitelist).

Isto é SÓ autorização — quais chat_ids têm permissão de acionar o bot. A
credencial usada para logar no Assyst é ÚNICA para todo mundo (decisão do
usuário, 2026-08-17: cadastrar a senha de cada colega não é viável) e mora em
`bot/services/credencial_servico.py`, separada daqui.

Guarda tambem um nome/apelido por chat_id — não vem do perfil do Telegram
(que a pessoa pode mudar a qualquer hora) para os logs ficarem previsíveis.
"""
from services import db


def _mapa() -> dict:
    """chat_id (str) -> nome. Mora no banco (services/db.py) desde 2026-09-28;
    antes era data/usuarios_bot.json."""
    return {r["chat_id"]: r["nome"] for r in
            db.consultar("SELECT chat_id, nome FROM bot_usuarios")}


def autorizado(chat_id) -> bool:
    return bool(db.consultar("SELECT 1 FROM bot_usuarios WHERE chat_id = ?",
                             (str(chat_id),)))


def nome_de(chat_id) -> str:
    """O apelido cadastrado para este chat_id ("" se não achar)."""
    return _mapa().get(str(chat_id), "")


def listar() -> dict:
    """Todo mundo liberado hoje, chat_id (str) -> nome/apelido."""
    return _mapa()


def cadastrar(chat_id, nome) -> None:
    """Libera o chat_id a falar com o bot — não envolve credencial nenhuma
    (ver `credencial_servico.py`).
    """
    nome = nome.strip()
    with db.transacao() as con:
        con.execute("INSERT OR REPLACE INTO bot_usuarios VALUES (?, ?)",
                    (str(chat_id), nome))
    print(f"OK: chat {chat_id} -> {nome!r} liberado(a) para usar o bot")


def remover(chat_id) -> None:
    with db.transacao() as con:
        con.execute("DELETE FROM bot_usuarios WHERE chat_id = ?",
                    (str(chat_id),))
