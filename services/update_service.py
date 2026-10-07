"""
services/update_service.py — Checagem e download de atualização, sem UI.

Usado pelo `atualizar.py --baixar` (chamado pelo `atualizar_automatic.bat`,
com o app FECHADO — desde 07/10 não há mais atualização pela tela):
  - versao_remota(): lê o version.json publicado no GitHub.
  - baixar_e_preparar(): baixa o zip e extrai para UPDATE_STAGING_DIR (fora
    da árvore do projeto); quem copia por cima do projeto é o atualizar.py.

Tudo por urllib, NÃO requests: na rede do TJCE (inspeção TLS corporativa) o
certificado raiz está no repositório do Windows, que o urllib usa, mas não no
bundle do certifi do requests. O download já tinha migrado por isso; a checagem
de versão continuava no requests e, quando falhava, respondia "nada novo" em
silêncio — agora o erro sobe para quem chamou mostrar.
"""
import json
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from services.paths import UPDATE_STAGING_DIR

VERSION_URL = "https://raw.githubusercontent.com/MiguelBatistaSilva/Automatic/main/version.json"


def versao_maior(remota: str, local: str) -> bool:
    try:
        r = tuple(int(x) for x in remota.strip().split("."))
        l = tuple(int(x) for x in local.strip().split("."))
        return r > l
    except Exception:
        return False


def versao_remota() -> tuple[str, str]:
    """(versão, url do zip) publicadas no GitHub. LEVANTA em erro de rede —
    quem chama decide o que dizer ao técnico."""
    req = urllib.request.Request(VERSION_URL, headers={"User-Agent": "Automatic-Updater"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("version", ""), data.get("download_url", "")


def baixar_e_preparar(download_url: str, versao_alvo: str, log) -> bool:
    """Baixa o zip e deixa pronto em UPDATE_STAGING_DIR, com um manifest.json
    dizendo pra qual versão e onde estão os arquivos extraídos. Não mexe no
    projeto — quem aplica de fato é `atualizar.py`, com o app fechado."""
    log(f"Baixando versão {versao_alvo}...", "info")
    zip_path = None
    try:
        # urllib (não requests) de propósito: em rede com inspeção TLS
        # corporativa, o certificado raiz costuma já estar confiável no
        # repositório do Windows, mas não no bundle do certifi que o
        # `requests` usa — urllib valida contra o do Windows.
        req = urllib.request.Request(download_url, headers={"User-Agent": "Automatic-Updater"})
        with urllib.request.urlopen(req, timeout=120) as resp, \
                tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            while True:
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
            zip_path = Path(f.name)
    except Exception as e:
        log(f"Falha ao baixar: {e}", "error")
        return False

    try:
        if UPDATE_STAGING_DIR.exists():
            shutil.rmtree(UPDATE_STAGING_DIR, ignore_errors=True)
        UPDATE_STAGING_DIR.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path) as z:
            z.extractall(UPDATE_STAGING_DIR)

        # O zip do GitHub extrai numa subpasta tipo "Automatic-main/".
        subdirs = [d for d in UPDATE_STAGING_DIR.iterdir() if d.is_dir()]
        if not subdirs:
            log("Zip extraído sem a pasta esperada.", "error")
            return False

        manifest = {"versao": versao_alvo, "origem": str(subdirs[0])}
        with open(UPDATE_STAGING_DIR / "manifest.json", "w", encoding="utf-8") as mf:
            json.dump(manifest, mf)
    except Exception as e:
        log(f"Falha ao preparar atualização: {e}", "error")
        return False
    finally:
        if zip_path is not None:
            zip_path.unlink(missing_ok=True)

    log(f"Versão {versao_alvo} baixada e pronta para aplicar.", "success")
    return True
