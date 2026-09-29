"""
services/credenciais.py — Armazenamento das credenciais do CATI/Assyst.

A matricula fica no banco (services/db.py, tabela app_config, chave
'matricula') desde 2026-09-28 — antes era data/credenciais.json.
A SENHA nunca vai para o disco: vai para o Cofre de Credenciais do Windows via
keyring, criptografada pelo SO e amarrada a conta Windows do usuario.
"""
import keyring

from services import db

# Nome do "servico" no Cofre do Windows. Aparece assim no Gerenciador de
# Credenciais, entao vale manter legivel.
SERVICO = "Automatic"


def _ler_matricula() -> str:
    r = db.consultar("SELECT valor FROM app_config WHERE chave = 'matricula'")
    return r[0]["valor"] if r else ""


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
    with db.transacao() as con:
        con.execute("INSERT OR REPLACE INTO app_config VALUES ('matricula', ?)",
                    (matricula,))


def apagar() -> None:
    matricula = _ler_matricula()
    if matricula:
        try:
            keyring.delete_password(SERVICO, matricula)
        except keyring.errors.PasswordDeleteError:
            pass
    with db.transacao() as con:
        con.execute("DELETE FROM app_config WHERE chave = 'matricula'")


def tem_credenciais() -> bool:
    return bool(carregar()[0])
