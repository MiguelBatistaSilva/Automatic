"""
services/requisicao_presets.py — valores pré-cadastrados para os campos do
/requisicao no bot (Telegram).

Motivo de existir: no celular, digitar cada campo da Requisição toda vez é
lento. Quem cadastra alguns valores fixos aqui (pela tela "Presets da
Requisição" no app) passa a escolher por BOTÃO no bot, em vez de digitar.

Campo SEM preset cadastrado cai para digitado — não trava o fluxo. Ver
`bot/commands/cmd_requisicao.py` para como isso decide o passo a passo.

Mora no banco (services/db.py, tabela requisicao_presets) desde 2026-09-28;
antes era data/requisicao_presets.json. A interface continua um dict
{campo: [valores]} porque cada CAMPO tem sua própria lista de valores.
"""
from services import db

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
    dados = {c: [] for c in CAMPOS_COM_PRESET}
    for r in db.consultar(
            "SELECT campo, valor FROM requisicao_presets ORDER BY campo, ordem"):
        if r["campo"] in dados:
            dados[r["campo"]].append(r["valor"])
    return dados


def salvar(presets: dict[str, list[str]]) -> None:
    """Substitui TODOS os presets pelo dict recebido (mesma semântica do JSON)."""
    with db.transacao() as con:
        con.execute("DELETE FROM requisicao_presets")
        for campo, valores in presets.items():
            # dict.fromkeys: tira repetidos mantendo a ordem (a chave primária
            # é campo+valor; repetido derrubaria a gravação inteira).
            for ordem, valor in enumerate(dict.fromkeys(valores)):
                con.execute(
                    "INSERT INTO requisicao_presets VALUES (?, ?, ?)",
                    (campo, valor, ordem))
