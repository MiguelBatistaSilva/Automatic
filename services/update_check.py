"""
services/update_check.py — Checagem de atualização SEM dependência de UI.

A lógica de comparar a versão local com o manifesto remoto (`version.json` no
GitHub) não tem nada de Qt. Ela vive aqui para poder ser usada tanto pelo
`updater.py` (Qt, `UpdateChecker`) quanto pelo app Reflex, sem importar PyQt6.
"""

import requests

VERSION_URL = "https://raw.githubusercontent.com/MiguelBatistaSilva/Automatic/main/version.json"


def _versao_maior(remota: str, local: str) -> bool:
    try:
        r = tuple(int(x) for x in remota.strip().split("."))
        l = tuple(int(x) for x in local.strip().split("."))
        return r > l
    except Exception:
        return False


def verificar_atualizacao(versao_atual: str) -> tuple[str, str] | None:
    """Consulta o manifesto remoto. Devolve (versao_remota, download_url) se houver
    versão maior que a instalada; senão None (inclusive em erro de rede)."""
    try:
        r = requests.get(VERSION_URL, timeout=10)
        r.raise_for_status()
        data = r.json()
        remota = data.get("version", "")
        url = data.get("download_url", "")
        if remota and _versao_maior(remota, versao_atual):
            return remota, url
    except Exception:
        return None
    return None
