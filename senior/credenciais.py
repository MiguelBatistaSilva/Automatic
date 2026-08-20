"""
senior/credenciais.py — Armazenamento das credenciais da Senior HCM (Ponto).

Cofre PRÓPRIO no keyring (`SERVICO`), separado do `services/credenciais.py`
(o do Assyst) — site e credencial diferentes, sem motivo pra cruzar. Mesma
lógica do `services/credenciais.py`: o usuário fica num JSON simples em
data/, a SENHA nunca vai para o disco. `data/` continua compartilhada de
propósito (ver services/paths.py) — é só o CÓDIGO da automação que fica
isolado do Assyst, não a pasta de dados do usuário.
"""
import json

import keyring

from services.paths import DATA_DIR

SERVICO = "Automatic-Ponto"

_PATH = DATA_DIR / "credenciais_ponto.json"


def _ler_usuario() -> str:
    if not _PATH.exists():
        return ""
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get("usuario", "")
    except (json.JSONDecodeError, OSError):
        return ""


def carregar() -> tuple[str, str]:
    """Devolve (usuario, senha). Retorna ("", "") se nao houver nada salvo."""
    usuario = _ler_usuario()
    if not usuario:
        return "", ""
    senha = keyring.get_password(SERVICO, usuario) or ""
    if not senha:
        return "", ""
    return usuario, senha


def salvar(usuario: str, senha: str) -> None:
    usuario = usuario.strip()
    senha = senha.strip()
    if not usuario or not senha:
        raise ValueError("Usuario e senha sao obrigatorios.")

    antigo = _ler_usuario()
    if antigo and antigo != usuario:
        try:
            keyring.delete_password(SERVICO, antigo)
        except keyring.errors.PasswordDeleteError:
            pass

    keyring.set_password(SERVICO, usuario, senha)
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump({"usuario": usuario}, f, ensure_ascii=False, indent=2)


def tem_credenciais() -> bool:
    return bool(carregar()[0])
