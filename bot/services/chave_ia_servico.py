"""
bot/services/chave_ia_servico.py — A chave de IA de CADA técnico no bot (10/10).

O Assistente no Telegram fala com a IA usando a chave de QUEM pediu: o plano
grátis da Groq limita tokens por minuto POR CHAVE (~6 mil por pedido, de
8 mil/minuto), então uma chave só para todos estouraria com dois técnicos ao
mesmo tempo. Decisão do usuário: cada técnico tem a sua.

Mesmo arranjo das credenciais do Assyst (credencial_servico.py): a chave fica
no Cofre do Windows da máquina que roda o bot, uma por chat_id e plataforma
(usuário "<chat_id>:<plataforma>"); o modelo escolhido (só o id, sem
segredo) fica no banco, em app_config ('bot_modelo_ia:<chat_id>').
"""
import keyring

from services import db
from services.agente import llm

SERVICO = "Automatic-Bot-IA"


def _usuario(chat_id, plataforma: str) -> str:
    return f"{chat_id}:{plataforma}"


def carregar_de(chat_id, plataforma: str) -> str:
    return keyring.get_password(SERVICO, _usuario(chat_id, plataforma)) or ""


def salvar_de(chat_id, plataforma: str, chave: str) -> None:
    p = llm.PLATAFORMAS.get(plataforma)
    chave = (chave or "").strip()
    if p is None:
        raise ValueError(f"Plataforma desconhecida: {plataforma}")
    if not chave:
        raise ValueError("Chave vazia.")
    if p.prefixo and not chave.startswith(p.prefixo):
        raise ValueError(f"A chave da {p.nome} começa com '{p.prefixo}'.")
    keyring.set_password(SERVICO, _usuario(chat_id, plataforma), chave)


def disponiveis_de(chat_id) -> list[str]:
    """Ids dos modelos (llm.MODELOS) com chave cadastrada por este chat_id."""
    return [m.id for m in llm.MODELOS.values() if carregar_de(chat_id, m.plataforma)]


def escolher_de(chat_id, modelo_id: str) -> None:
    if modelo_id not in llm.MODELOS:
        raise ValueError(f"Modelo desconhecido: {modelo_id}")
    with db.transacao() as con:
        con.execute("INSERT OR REPLACE INTO app_config VALUES (?, ?)",
                    (f"bot_modelo_ia:{chat_id}", modelo_id))


def escolhido_de(chat_id) -> tuple[str, str]:
    """(modelo, chave) que este técnico usa: o último escolhido, se ainda
    tiver chave; senão o primeiro com chave. ("", "") = nenhuma chave."""
    ok = disponiveis_de(chat_id)
    if not ok:
        return "", ""
    r = db.consultar("SELECT valor FROM app_config WHERE chave = ?",
                     (f"bot_modelo_ia:{chat_id}",))
    modelo = r[0]["valor"] if r and r[0]["valor"] in ok else ok[0]
    return modelo, carregar_de(chat_id, llm.MODELOS[modelo].plataforma)
