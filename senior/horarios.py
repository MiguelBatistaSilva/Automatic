"""
senior/horarios.py — Lembra os ultimos horarios de ponto digitados.

Sem senha nem nada sensivel aqui, so os 4 textos "HH:MM" — por isso vai direto
num JSON em data/ (ver services/paths.py), sem precisar do Cofre do Windows como
senior/credenciais.py.
"""
import json

from services.paths import DATA_DIR

_PATH = DATA_DIR / "horarios_ponto.json"


def carregar() -> tuple[str, str, str, str]:
    """Devolve (horario1..4). ("", "", "", "") se nao houver nada salvo."""
    if not _PATH.exists():
        return "", "", "", ""
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            dados = json.load(f)
    except (json.JSONDecodeError, OSError):
        return "", "", "", ""
    return (
        dados.get("horario1", ""),
        dados.get("horario2", ""),
        dados.get("horario3", ""),
        dados.get("horario4", ""),
    )


def salvar(horario1: str, horario2: str, horario3: str, horario4: str) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {
                "horario1": horario1,
                "horario2": horario2,
                "horario3": horario3,
                "horario4": horario4,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
