"""
bot/credencial_servico.py — a credencial que cada pessoa usa para logar no
Assyst, por chat_id do Telegram.

Decisão do usuário (2026-08-26): a credencial única (2026-08-17) foi
REVERTIDA. Cada pessoa cadastra a própria matrícula/senha com /credencial
(bot/cmd_credencial.py) e a automação loga como ELA quando ela pede uma
ação — em vez de tudo passar pela mesma conta de serviço. A whitelist
(`bot/usuarios.py`) continua separada: aquilo é só autorização (quem pode
falar com o bot), isto aqui é a identidade usada no Assyst.

RISCO QUE ISSO NÃO REMOVE, DE PROPÓSITO ACEITO: todas as credenciais
continuam no Cofre do Windows desta MESMA máquina — quem tiver o nível de
acesso desta conta do Windows lê a senha de qualquer pessoa em texto puro.
Trocar "uma credencial exposta" por "N credenciais concentradas aqui" foi
decisão consciente do usuário, não um cofre de verdade multi-tenant.

POR QUE SEPARADO de `services/credenciais.py` (o cofre do app Reflex): mesmo
motivo de antes — aquele guarda a matrícula de quem usa o APP DESKTOP naquela
máquina, e trocar de conta ali apaga a senha anterior do cofre. Nome de
serviço próprio no Cofre do Windows (`SERVICO_BOT`) evita qualquer colisão.

ONDE MORA: tabela `bot_credenciais` do banco (services/db.py), {chat_id:
matricula}, desde 2026-09-28. Antes era data/credencial_bot.json — a
importação desse arquivo (inclusive do formato antigo de credencial única,
de antes de 2026-08-26) é feita uma vez só pelo próprio db.py.
"""
import keyring

from services import db

SERVICO_BOT = "Automatic-Bot"


def _ler_mapa() -> dict[str, str]:
    """{chat_id (str): matricula}."""
    return {r["chat_id"]: r["matricula"] for r in
            db.consultar("SELECT chat_id, matricula FROM bot_credenciais")}


def carregar_de(chat_id) -> tuple[str, str]:
    """Devolve (matricula, senha) da credencial cadastrada por este chat_id.

    ("", "") se a pessoa ainda não cadastrou — quem chama trata isso como
    "essa pessoa precisa mandar /credencial primeiro".
    """
    matricula = _ler_mapa().get(str(chat_id), "")
    if not matricula:
        return "", ""
    senha = keyring.get_password(SERVICO_BOT, matricula) or ""
    if not senha:
        return "", ""
    return matricula, senha


def configurada_de(chat_id) -> bool:
    return bool(_ler_mapa().get(str(chat_id), ""))


def carregar_token() -> str:
    """Devolve o token do bot do Telegram, ou "" se ainda não configurado."""
    return keyring.get_password(SERVICO_BOT, "telegram_bot_token") or ""


def salvar_token(token: str) -> None:
    token = token.strip()
    if not token:
        raise ValueError("Token e obrigatorio.")
    keyring.set_password(SERVICO_BOT, "telegram_bot_token", token)


def salvar_de(chat_id, matricula: str, senha: str) -> None:
    matricula = matricula.strip()
    senha = senha.strip()
    if not matricula or not senha:
        raise ValueError("Matricula e senha sao obrigatorias.")

    chat_id = str(chat_id)
    mapa = _ler_mapa()
    antiga = mapa.get(chat_id, "")

    # Se a matricula deste chat_id mudou, so apaga a entrada antiga do cofre
    # se NENHUM OUTRO chat_id ainda depender dela — senao apagaria a senha de
    # outra pessoa que por acaso tenha a mesma matricula cadastrada antes.
    if antiga and antiga != matricula and antiga not in mapa.values():
        try:
            keyring.delete_password(SERVICO_BOT, antiga)
        except keyring.errors.PasswordDeleteError:
            pass

    keyring.set_password(SERVICO_BOT, matricula, senha)
    with db.transacao() as con:
        con.execute("INSERT OR REPLACE INTO bot_credenciais VALUES (?, ?)",
                    (chat_id, matricula))


def remover_de(chat_id) -> None:
    """Esquece a credencial deste chat_id (mantida no cofre se outro
    chat_id ainda usar a mesma matricula)."""
    chat_id = str(chat_id)
    mapa = _ler_mapa()
    matricula = mapa.pop(chat_id, None)
    if matricula is None:
        return
    with db.transacao() as con:
        con.execute("DELETE FROM bot_credenciais WHERE chat_id = ?", (chat_id,))
    if matricula not in mapa.values():
        try:
            keyring.delete_password(SERVICO_BOT, matricula)
        except keyring.errors.PasswordDeleteError:
            pass
