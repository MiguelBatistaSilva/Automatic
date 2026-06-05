import requests
import zipfile
import tempfile
import subprocess
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

VERSION_URL = "https://raw.githubusercontent.com/MiguelBatistaSilva/Automatic/main/version.json"


def _versao_maior(remota: str, local: str) -> bool:
    try:
        r = tuple(int(x) for x in remota.strip().split("."))
        l = tuple(int(x) for x in local.strip().split("."))
        return r > l
    except Exception:
        return False


class UpdateChecker(QThread):
    nova_versao = pyqtSignal(str, str)  # (versao_remota, download_url)

    def __init__(self, versao_atual: str):
        super().__init__()
        self.versao_atual = versao_atual

    def run(self):
        try:
            r = requests.get(VERSION_URL, timeout=10)
            r.raise_for_status()
            data = r.json()
            remota = data.get("version", "")
            url = data.get("download_url", "")
            if remota and _versao_maior(remota, self.versao_atual):
                self.nova_versao.emit(remota, url)
        except Exception:
            pass


class UpdateDownloader(QThread):
    progresso = pyqtSignal(int)
    concluido = pyqtSignal(str)  # caminho da pasta extraida
    erro = pyqtSignal(str)

    def __init__(self, download_url: str, app_dir: str):
        super().__init__()
        self.download_url = download_url
        self.app_dir = app_dir

    def run(self):
        try:
            r = requests.get(self.download_url, stream=True, timeout=60)
            r.raise_for_status()

            total = int(r.headers.get("content-length", 0))
            baixado = 0
            tmp_dir = Path(tempfile.mkdtemp())
            tmp_zip = tmp_dir / "update.zip"

            with open(tmp_zip, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    baixado += len(chunk)
                    if total:
                        self.progresso.emit(int(baixado / total * 100))

            with zipfile.ZipFile(tmp_zip, "r") as z:
                z.extractall(tmp_dir)
            tmp_zip.unlink()

            subdirs = [d for d in tmp_dir.iterdir() if d.is_dir()]
            if not subdirs:
                self.erro.emit("Pasta extraida nao encontrada.")
                return

            self.concluido.emit(str(subdirs[0]))

        except Exception as e:
            self.erro.emit(str(e))


def aplicar_atualizacao(pasta_extraida: str, app_dir: str) -> None:
    bat_path = Path(app_dir) / "_update.bat"
    vbs_path = Path(app_dir) / "iniciar_automatic.vbs"

    # Espera ~4s para o app fechar antes de sobrescrever os arquivos. Usamos
    # 'ping' em vez de 'timeout' porque 'timeout' exige um console interativo e
    # falha quando o processo roda oculto (CREATE_NO_WINDOW).
    bat = (
        "@echo off\n"
        "ping 127.0.0.1 -n 5 > nul\n"
        f'robocopy "{pasta_extraida}" "{app_dir}" /E /IS /IT '
        '/XD "data" ".venv" "pacotes_automacao" /NFL /NDL /NJH /NJS\n'
        f'rd /S /Q "{pasta_extraida}"\n'
        f'del /F /Q "{bat_path}"\n'
        f'start "" wscript.exe "{vbs_path}"\n'
    )
    bat_path.write_text(bat, encoding="utf-8")
    # CREATE_NO_WINDOW: o processo de atualizacao roda oculto, sem piscar um CMD.
    subprocess.Popen(
        ["cmd.exe", "/c", str(bat_path)],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
