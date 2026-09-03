"""
services/requisicao_presets.py — valores pré-cadastrados para os campos do
/requisicao no bot (Telegram).

Motivo de existir: no celular, digitar cada campo da Requisição toda vez é
lento. Quem cadastra alguns valores fixos aqui (pela tela "Presets da
Requisição" no app) passa a escolher por BOTÃO no bot, em vez de digitar.

Campo SEM preset cadastrado cai para digitado — não trava o fluxo. Ver
`bot/commands/cmd_requisicao.py` para como isso decide o passo a passo.

Mesmo padrão de `services/kb_store.py` (list/dict simples em JSON, sem
banco). Aqui é dict porque cada CAMPO tem sua própria lista de valores.
"""
import json

from services.paths import DATA_DIR

_PATH = DATA_DIR / "requisicao_presets.json"

# Campos que aceitam preset no bot — bate com requisicao_campos.ORDEM_COLUNAS
# menos usuario_afetado e descricao (esses dois são sempre digitados, texto
# livre por natureza: matrícula muda a cada chamado, descrição é única).
CAMPOS_COM_PRESET: tuple[str, ...] = (
    "edificio", "resumo", "item", "item_b", "categoria",
    "grupo_atribuido", "usuario_atribuido",
)


def carregar() -> dict[str, list[str]]:
    """{campo: [valores]}. Sempre devolve as 7 chaves, mesmo vazias —
    quem usa não precisa checar `.get(campo, [])` toda vez."""
    dados = {}
    if _PATH.exists():
        try:
            with open(_PATH, "r", encoding="utf-8") as f:
                dados = json.load(f)
        except (json.JSONDecodeError, OSError):
            dados = {}
    return {c: dados.get(c, []) for c in CAMPOS_COM_PRESET}


def salvar(presets: dict[str, list[str]]) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(presets, f, ensure_ascii=False, indent=2)
