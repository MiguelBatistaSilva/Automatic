"""
services/update_service.py — Checagem e download de atualização, sem UI.

Duas responsabilidades, ambas seguras de rodar com o app Reflex ABERTO (nenhuma
delas toca em arquivo nenhum do projeto):
  - verificar(): compara a versão instalada com o manifesto remoto (version.json
    publicado no GitHub).
  - baixar_e_preparar(): baixa o zip da versão nova e extrai para
    UPDATE_STAGING_DIR (fora da árvore do projeto — ver services/paths.py).

APLICAR de fato (trocar os arquivos do projeto pelos baixados) é outra etapa,
feita por `atualizar.py` na raiz, sempre com o app FECHADO — ver o docstring de
lá para o porquê dessa separação.
"""
import json
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import requests

from services.paths import UPDATE_STAGING_DIR

VERSION_URL = "https://raw.githubusercontent.com/MiguelBatistaSilva/Automatic/main/version.json"


def _versao_maior(remota: str, local: str) -> bool:
    try:
        r = tuple(int(x) for x in remota.strip().split("."))
        l = tuple(int(x) for x in local.strip().split("."))
        return r > l
    except Exception:
        return False


def verificar(versao_atual: str) -> tuple[str, str] | None:
    """Consulta o manifesto remoto. Devolve (versao_remota, download_url) se
    houver versão maior que a instalada; senão None (inclusive em erro de rede
    — sem internet ou GitHub fora do ar não deve travar o pop-up, só dizer que
    não achou nada novo)."""
    try:
        r = requests.get(VERSION_URL, timeout=10)
        r.raise_for_status()
        data = r.json()
        remota = data.get("version", "")
        url = data.get("download_url", "")
        if remota and url and _versao_maior(remota, versao_atual):
            return remota, url
    except Exception:
        return None
    return None


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
