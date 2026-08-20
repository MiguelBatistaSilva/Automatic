"""
bot/credencial_servico.py — a credencial UNICA que o bot usa para logar no
Assyst, seja qual for o chat_id que pediu a ação.

Decisão do usuário (2026-08-17): cadastrar a credencial de cada colega não é
viável. O bot passa a rodar sempre com UMA conta só (matrícula/senha
combinadas por ele) — quem fala com o bot só precisa estar na whitelist
(ver `bot/usuarios.py`), não precisa mais ter a própria senha configurada.

POR QUE SEPARADO de `services/credenciais.py` (o cofre do app Reflex): aquele
módulo guarda UMA matrícula (a de quem usa o app naquela máquina), e o
`salvar()` de lá APAGA do cofre a senha da matrícula ANTERIOR sempre que a
matrícula muda. Se o bot usasse o MESMO nome de serviço no keyring, alguém
trocando a própria credencial pela tela do app, na mesma máquina, apagaria em
silêncio a credencial que o bot depende para funcionar — os dois cofres
precisam ser independentes. `SERVICO_BOT` é o nome próprio no Cofre do
Windows; nunca colide com `services.credenciais.SERVICO` ("Automatic").

Mesmo padrão de guarda do app: matrícula num JSON simples em `data/`, senha
nunca no disco — só no Cofre do Windows via keyring.
"""
import json

import keyring

from services.paths import DATA_DIR

SERVICO_BOT = "Automatic-Bot"

_PATH = DATA_DIR / "credencial_bot.json"


def _ler_matricula() -> str:
    if not _PATH.exists():
        return ""
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get("matricula", "")
    except (json.JSONDecodeError, OSError):
        # Arquivo corrompido: trata como "nao configurada" em vez de derrubar
        # o bot na subida.
        return ""


def carregar() -> tuple[str, str]:
    """Devolve (matricula, senha) da credencial única do bot.

    ("", "") se ainda não foi configurada — quem chama trata isso como "bot
    não consegue logar", igual ao app quando não há credencial salva.
    """
    matricula = _ler_matricula()
    if not matricula:
        return "", ""
    senha = keyring.get_password(SERVICO_BOT, matricula) or ""
    if not senha:
        return "", ""
    return matricula, senha


def configurada() -> bool:
    return bool(_ler_matricula())


def carregar_token() -> str:
    """Devolve o token do bot do Telegram, ou "" se ainda não configurado."""
    return keyring.get_password(SERVICO_BOT, "telegram_bot_token") or ""


def salvar_token(token: str) -> None:
    token = token.strip()
    if not token:
        raise ValueError("Token e obrigatorio.")
    keyring.set_password(SERVICO_BOT, "telegram_bot_token", token)


def salvar(matricula: str, senha: str) -> None:
    matricula = matricula.strip()
    senha = senha.strip()
    if not matricula or not senha:
        raise ValueError("Matricula e senha sao obrigatorias.")

    # Se a matricula mudou, remove a entrada antiga do cofre do BOT (nao do
    # cofre do app) para nao deixar senha orfa la dentro.
    antiga = _ler_matricula()
    if antiga and antiga != matricula:
        try:
            keyring.delete_password(SERVICO_BOT, antiga)
        except keyring.errors.PasswordDeleteError:
            pass

    keyring.set_password(SERVICO_BOT, matricula, senha)
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump({"matricula": matricula}, f, ensure_ascii=False, indent=2)
