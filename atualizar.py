"""
atualizar.py — Atualiza o Automatic. SEMPRE com o app FECHADO.

Dois modos:

  1) `atualizar.py --baixar` — chamado pelo `atualizar_automatic.bat` (07/10,
     substituiu o ícone de atualização da tela, que vivia dando erro). Confere
     que o Automatic está fechado, compara a versão local com o version.json do
     GitHub, baixa o zip (services/update_service.py), faz backup em _backup/ e
     copia por cima do projeto. Mostra tudo na tela e devolve código de saída
     (0 = ok ou já atualizado; 1 = erro) para o .bat.

  2) sem argumentos — roda toda vez que `iniciar_automatic.bat` sobe, ANTES do
     'reflex run': aplica uma atualização que tenha ficado baixada e não
     aplicada (staging). Silencioso e FAIL-OPEN: erro só vai para o
     `_update.log`, nunca impede o app de subir.

POR QUE COM O APP FECHADO: o `reflex run` observa a pasta do projeto INTEIRA e
reinicia o backend a cada arquivo alterado (mesmo mecanismo do bug do hot-reload
com os checkpoints .tmp). Trocar centenas de arquivos com ele de pé dispararia
uma tempestade de restarts no meio da cópia.

O modo 2 usa só biblioteca padrão (é o primeiro script do .bat, antes de
qualquer garantia sobre o ambiente); o modo 1 importa services/ de propósito,
porque roda com a .venv pronta.
"""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STAGING_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Automatic" / "update_pendente"
BACKUP_DIR = BASE_DIR / "_backup"
LOG_FILE = BASE_DIR / "_update.log"

# Pastas que NUNCA são copiadas (nem no update, nem no backup): pesadas ou de runtime.
EXCLUIR_DIRS = [".venv", ".web", ".states", "_backup", ".git", "__pycache__"]
# Arquivos protegidos de sobrescrita:
#   iniciar_automatic.bat / iniciar_bot.bat -> sobrescrever um .bat EM EXECUÇÃO
#     corrompe o Windows; o bot roda pelo iniciar_bot.bat numa máquina à parte,
#     que pode estar de pé na hora em que uma atualização é aplicada pela tela.
#   _update.log -> nosso próprio log
#   atualizar_automatic.bat -> é ELE que está rodando durante a atualização.
EXCLUIR_FILES = ["iniciar_automatic.bat", "iniciar_bot.bat", "atualizar_automatic.bat",
                 "_update.log"]


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


def _versao_local() -> str:
    """Lida do version.py como texto: depois da cópia, o módulo já importado
    estaria desatualizado."""
    import re
    texto = (BASE_DIR / "version.py").read_text(encoding="utf-8")
    m = re.search(r'VERSION\s*=\s*"([^"]+)"', texto)
    return m.group(1) if m else "0"


def _app_aberto() -> list[str]:
    """Processos rodando de dentro da .venv DESTE projeto (reflex, python do
    app ou do bot), tirando este próprio script e o pai dele. Lista vazia =
    pode atualizar. Se a consulta falhar, devolve [] e o .bat já pediu ao
    técnico para fechar o app antes."""
    venv = str(BASE_DIR / ".venv").lower()
    ps = ("Get-CimInstance Win32_Process | "
          "Select-Object ProcessId,Name,ExecutablePath | ConvertTo-Json -Compress")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, timeout=30)
        procs = json.loads(r.stdout or "[]")
    except Exception:
        return []
    meus = {os.getpid(), os.getppid()}
    return sorted({p["Name"] for p in procs
                   if (p.get("ExecutablePath") or "").lower().startswith(venv)
                   and p.get("ProcessId") not in meus})


def baixar_e_aplicar() -> int:
    """Modo do atualizar_automatic.bat. Devolve o código de saída."""
    sys.path.insert(0, str(BASE_DIR))
    from services.update_service import baixar_e_preparar, versao_maior, versao_remota

    abertos = _app_aberto()
    if abertos:
        log(f"O Automatic parece estar ABERTO ({', '.join(abertos)}). "
            "Feche a janela do Automatic (e a do bot, se houver) e rode de novo.")
        return 1

    local = _versao_local()
    log(f"Versão instalada: {local}")
    try:
        remota, url = versao_remota()
    except Exception as e:
        log(f"Não consegui consultar a versão no GitHub: {e}")
        return 1
    if not remota or not url:
        log("O version.json do GitHub veio sem versão ou sem link de download.")
        return 1
    if not versao_maior(remota, local):
        log(f"Já está na versão mais recente ({local}). Nada a fazer.")
        return 0

    log(f"Versão nova disponível: {remota}")
    if not baixar_e_preparar(url, remota, lambda msg, tipo="info": log(msg)):
        return 1
    if not aplicar_pendente():
        log("A atualização NÃO foi aplicada (veja as linhas acima).")
        return 1
    log(f"Pronto: Automatic atualizado para {remota}. Pode abrir o app.")
    return 0


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] == "--baixar":
        sys.exit(baixar_e_aplicar())

    aplicar_pendente()


if __name__ == "__main__":
    main()
