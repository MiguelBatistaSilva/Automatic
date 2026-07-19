"""
services/credenciais.py — Armazenamento das credenciais do CATI/Assyst.

A matricula fica num JSON simples em services/data/ (mesmo padrao do kb_store).
A SENHA nunca vai para o disco: vai para o Cofre de Credenciais do Windows via
keyring, criptografada pelo SO e amarrada a conta Windows do usuario.

A pasta 'data' e excluida do robocopy em updater.py, entao as credenciais
sobrevivem as atualizacoes do app.
"""
import json
from pathlib import Path

import keyring

# Nome do "servico" no Cofre do Windows. Aparece assim no Gerenciador de
# Credenciais, entao vale manter legivel.
SERVICO = "Automatic"

_PATH = Path(__file__).parent / "data" / "credenciais.json"


def _ler_matricula() -> str:
    if not _PATH.exists():
        return ""
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get("matricula", "")
    except (json.JSONDecodeError, OSError):
        # Arquivo corrompido ou ilegivel: trata como "sem credencial salva"
        # em vez de derrubar o app na abertura.
        return ""


def carregar() -> tuple[str, str]:
    """Devolve (matricula, senha). Retorna ("", "") se nao houver nada salvo."""
    matricula = _ler_matricula()
    if not matricula:
        return "", ""
    senha = keyring.get_password(SERVICO, matricula) or ""
    if not senha:
        # Matricula salva mas senha ausente do cofre (ex.: cofre limpo pelo
        # usuario). Sem senha nao da para logar, entao e o mesmo que nada.
        return "", ""
    return matricula, senha


def salvar(matricula: str, senha: str) -> None:
    matricula = matricula.strip()
    senha = senha.strip()
    if not matricula or not senha:
        raise ValueError("Matricula e senha sao obrigatorias.")

    # Se a matricula mudou, remove a entrada antiga do cofre para nao deixar
    # senha orfa la dentro.
    antiga = _ler_matricula()
    if antiga and antiga != matricula:
        try:
            keyring.delete_password(SERVICO, antiga)
        except keyring.errors.PasswordDeleteError:
            pass

    keyring.set_password(SERVICO, matricula, senha)
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump({"matricula": matricula}, f, ensure_ascii=False, indent=2)


def apagar() -> None:
    matricula = _ler_matricula()
    if matricula:
        try:
            keyring.delete_password(SERVICO, matricula)
        except keyring.errors.PasswordDeleteError:
            pass
    _PATH.unlink(missing_ok=True)


def tem_credenciais() -> bool:
    return bool(carregar()[0])
