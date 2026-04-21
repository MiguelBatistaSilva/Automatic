import json
from pathlib import Path

_KB_PATH = Path(__file__).parent / "data" / "kb_configs.json"


def carregar() -> list[dict]:
    if not _KB_PATH.exists():
        return []
    with open(_KB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def salvar(entries: list[dict]) -> None:
    _KB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_KB_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
