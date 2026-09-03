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

Formato do arquivo (`data/credencial_bot.json`): {chat_id (str): matricula}.
MIGRAÇÃO AUTOMÁTICA: se o arquivo ainda estiver no formato antigo
(`{"matricula": "..."}`, uma credencial só), a primeira leitura converte para
o novo formato associando essa matrícula ao chat_id do Miguel (dono da
credencial que já existia) e regrava o arquivo — sem precisar de script
separado nem de qualquer pessoa recadastrar o que já funcionava.
"""
import json

import keyring

from services.paths import DATA_DIR

SERVICO_BOT = "Automatic-Bot"

# chat_id do Miguel (usuarios_bot.json) — dono da credencial única que já
# existia antes da migração para credencial por pessoa (2026-08-26).
_CHAT_ID_MIGRACAO = "1070692564"

_PATH = DATA_DIR / "credencial_bot.json"


def _ler_mapa() -> dict[str, str]:
    """{chat_id (str): matricula}. Migra do formato antigo na primeira leitura."""
    if not _PATH.exists():
        return {}
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            dados = json.load(f)
    except (json.JSONDecodeError, OSError):
        # Arquivo corrompido: trata como "ninguem configurado" em vez de
        # derrubar o bot na subida.
        return {}

    if "matricula" in dados:
        # Formato antigo (credencial unica). A senha ja esta no keyring sob
        # essa matricula (nome do servico nao mudou) — so falta associar ao
        # chat_id do dono e regravar no formato novo.
        mapa = {_CHAT_ID_MIGRACAO: dados["matricula"]}
        _gravar_mapa(mapa)
        return mapa

    return dados


def _gravar_mapa(mapa: dict[str, str]) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(mapa, f, ensure_ascii=False, indent=2)


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
    mapa[chat_id] = matricula
    _gravar_mapa(mapa)


def remover_de(chat_id) -> None:
    """Esquece a credencial deste chat_id (mantida no cofre se outro
    chat_id ainda usar a mesma matricula)."""
    chat_id = str(chat_id)
    mapa = _ler_mapa()
    matricula = mapa.pop(chat_id, None)
    if matricula is None:
        return
    _gravar_mapa(mapa)
    if matricula not in mapa.values():
        try:
            keyring.delete_password(SERVICO_BOT, matricula)
        except keyring.errors.PasswordDeleteError:
            pass
