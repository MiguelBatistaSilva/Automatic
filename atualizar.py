"""
atualizar.py — Aplica a atualização pendente do Automatic (staging -> projeto).

Roda em DOIS momentos, sempre com o Reflex FECHADO:

  1) toda vez que `iniciar_automatic.bat` sobe, ANTES do 'reflex run' — silencioso,
     só faz alguma coisa se `state/update_state.py` já deixou uma atualização
     baixada e pronta (ver UPDATE_STAGING_DIR em services/paths.py).

  2) quando o usuário clica em "Reiniciar e aplicar" no pop-up de Atualização —
     nesse caso é chamado como `atualizar.py --reiniciar <pid>`: mata a árvore de
     processos do Reflex (o próprio `reflex run` sobe um processo de frontend
     como filho; matar só o processo principal deixaria esse filho preso na
     porta), aplica a atualização e sobe o `iniciar_automatic.bat` de novo sozinho.

POR QUE ISSO NÃO ACONTECE COM O APP ABERTO: o `reflex run` (modo dev, como este
projeto sempre roda) observa a pasta do projeto INTEIRA e reinicia o backend
sozinho a cada arquivo alterado — é o mesmo mecanismo que já causou o bug do
hot-reload com os checkpoints (.tmp). Trocar centenas de arquivos de uma vez com
o processo de pé ia disparar uma tempestade de restarts no meio da cópia. O
DOWNLOAD (services/update_service.py) já roda com o app aberto, mas só grava
fora da árvore do projeto — só a TROCA de arquivos, aqui, precisa do app fechado.

FAIL-OPEN: qualquer erro aqui só é logado (`_update.log`) — nunca impede o
`iniciar_automatic.bat` de seguir para o 'reflex run'.

Só biblioteca padrão de propósito: é o primeiro script a rodar no `.bat`, antes
de qualquer garantia sobre o estado do ambiente.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STAGING_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Automatic" / "update_pendente"
BACKUP_DIR = BASE_DIR / "_backup"
LOG_FILE = BASE_DIR / "_update.log"

# Pastas que NUNCA são copiadas (nem no update, nem no backup): pesadas ou de runtime.
EXCLUIR_DIRS = [".venv", ".web", ".states", "_backup", ".git", "__pycache__"]
# Arquivos protegidos de sobrescrita:
#   iniciar_automatic.bat  -> sobrescrever um .bat EM EXECUÇÃO corrompe o Windows
#   _update.log             -> nosso próprio log
EXCLUIR_FILES = ["iniciar_automatic.bat", "_update.log"]


def log(msg: str) -> None:
    linha = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(linha)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except Exception:
        pass


def _robocopy(origem: Path, destino: Path, excluir_arquivos: bool) -> int:
    """Copia origem->destino de forma ADITIVA (sem /MIR e sem /PURGE: nunca
    apaga nada no destino — é assim que dados locais em data/ sobrevivem sem
    precisar de exclusão nenhuma, ver services/paths.py). Devolve o código do
    robocopy (0-7 = sucesso; >=8 = erro real)."""
    cmd = ["robocopy", str(origem), str(destino), "/E",
           "/NFL", "/NDL", "/NJH", "/NJS", "/NP", "/R:2", "/W:2"]
    for d in EXCLUIR_DIRS:
        cmd += ["/XD", d]
    if excluir_arquivos:
        for f in EXCLUIR_FILES:
            cmd += ["/XF", f]
    return subprocess.run(cmd, capture_output=True, text=True).returncode


def _fazer_backup() -> None:
    """Guarda o estado atual em _backup/ antes de trocar — rede de segurança.
    Diferente do robocopy da atualização, aqui NÃO excluímos arquivos: queremos
    o backup completo, .env-equivalentes (credenciais.json etc.) inclusive."""
    if BACKUP_DIR.exists():
        shutil.rmtree(BACKUP_DIR, ignore_errors=True)
    BACKUP_DIR.mkdir(exist_ok=True)
    _robocopy(BASE_DIR, BACKUP_DIR, excluir_arquivos=False)


def aplicar_pendente() -> bool:
    """Se `services/update_service.baixar_e_preparar` já deixou uma atualização
    pronta, aplica. Devolve True se aplicou algo."""
    manifest_path = STAGING_DIR / "manifest.json"
    if not manifest_path.exists():
        return False

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        origem = Path(manifest["origem"])
        versao = manifest.get("versao", "?")
        if not origem.exists():
            log("Staging incompleto (pasta de origem sumiu). Ignorando.")
            return False

        log(f"Aplicando atualização para {versao}...")
        log("Fazendo backup da versão atual em _backup/...")
        _fazer_backup()

        codigo = _robocopy(origem, BASE_DIR, excluir_arquivos=True)
        if codigo >= 8:
            log(f"ERRO no robocopy (código {codigo}). Restaure de _backup/ se necessário.")
            return False

        log(f"Atualização para {versao} aplicada com sucesso.")
        return True
    except Exception as e:
        log(f"Atualização ignorada por erro: {e}")
        return False
    finally:
        shutil.rmtree(STAGING_DIR, ignore_errors=True)


def _reiniciar(pid: str) -> None:
    log(f"Encerrando o Automatic (PID {pid}) para atualizar...")
    subprocess.run(["taskkill", "/PID", pid, "/T", "/F"], capture_output=True)
    time.sleep(2)  # da tempo do Windows soltar os arquivos abertos

    aplicar_pendente()

    log("Reabrindo o Automatic...")
    os.startfile(str(BASE_DIR / "iniciar_automatic.bat"))  # noqa: (só existe no Windows)


def main() -> None:
    if len(sys.argv) >= 3 and sys.argv[1] == "--reiniciar":
        _reiniciar(sys.argv[2])
        return

    aplicar_pendente()


if __name__ == "__main__":
    main()
