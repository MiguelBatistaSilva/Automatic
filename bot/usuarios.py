"""
bot/usuarios.py — quem pode falar com o bot (whitelist).

Isto é SÓ autorização — quais chat_ids têm permissão de acionar o bot. A
credencial usada para logar no Assyst é ÚNICA para todo mundo (decisão do
usuário, 2026-08-17: cadastrar a senha de cada colega não é viável) e mora em
`bot/services/credencial_servico.py`, separada daqui.

Guarda tambem um nome/apelido por chat_id — não vem do perfil do Telegram
(que a pessoa pode mudar a qualquer hora) para os logs ficarem previsíveis.
"""
import json

from services.paths import DATA_DIR

_PATH = DATA_DIR / "usuarios_bot.json"


def _mapa() -> dict:
    if not _PATH.exists():
        return {}
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # Arquivo corrompido: trata como "ninguem autorizado" em vez de derrubar
        # o bot. Numa fronteira de seguranca, falhar fechado e o unico jeito.
        return {}


def autorizado(chat_id) -> bool:
    return str(chat_id) in _mapa()


def nome_de(chat_id) -> str:
    """O apelido cadastrado para este chat_id ("" se não achar)."""
    return _mapa().get(str(chat_id), "")


def listar() -> dict:
    """Todo mundo liberado hoje, chat_id (str) -> nome/apelido."""
    return _mapa()


def cadastrar(chat_id, nome) -> None:
    """Libera o chat_id a falar com o bot — não envolve credencial nenhuma
    (ver `credencial_servico.py`, configurada uma vez só para o bot inteiro).
    """
    nome = nome.strip()
    mapa = _mapa()
    mapa[str(chat_id)] = nome
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(mapa, f, ensure_ascii=False, indent=2)
    print(f"OK: chat {chat_id} -> {nome!r} liberado(a) para usar o bot")


def remover(chat_id) -> None:
    mapa = _mapa()
    if mapa.pop(str(chat_id), None) is None:
        return
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(mapa, f, ensure_ascii=False, indent=2)
