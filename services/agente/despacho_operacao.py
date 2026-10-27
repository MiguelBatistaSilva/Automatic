"""
services/agente/despacho_operacao.py — Script de DESPACHO de equipamento ao Serviço
de Operações (20/10).

"Preciso condenar um teclado..." / "mandar a máquina ... para a Operação": o
chamado vai PAUSADO pela mesma ação 'Aguardando Info do Fornecedor', só que
com este script no lugar do texto livre. Aqui só se MONTA o texto; quem
escreve no Assyst é o fluxo de sempre (services/fluxos/flow_fornecedor_pw.py).

Testes e defeito são obrigatórios. Desde 26/10 vêm dos MODELOS POR DEFEITO
da equipe (services/agente/conhecimento/chamados/despachos.md — edite lá):
a IA só escolhe o modelo. Tipo ainda sem modelo cai no script genérico
(SCRIPTS abaixo), com aviso para o técnico conferir.
Teclado, mouse, webcam e caixa de som não têm tombo: a linha nem sai.
"""

import unicodedata

from services.agente import conhecimento

# Tipos da linha "Tipo:" do script, na ordem em que aparecem.
PRINCIPAIS = ["Computador", "Notebook", "Monitor", "Impressora"]
# Os que vão em "( ) Outros Qual?".
OUTROS = ["Teclado", "Mouse", "Webcam", "Caixa de som"]
TIPOS = PRINCIPAIS + OUTROS

# Script genérico por tipo: (testes realizados, defeito apresentado). RESERVA
# para tipo sem modelo em despachos.md (hoje Notebook e Impressora) ou se o
# arquivo sumir; os modelos da equipe valem mais.
SCRIPTS: dict[str, tuple[list[str], list[str]]] = {
    "Computador": (["Feita mudança de cabo de força", "Testado em outra tomada"],
                   ["Computador não liga"]),
    "Notebook": (["Feita mudança de carregador", "Testado em outra tomada"],
                 ["Notebook não liga"]),
    "Monitor": (["Feita mudança de cabo de força", "Testado em outro micro"],
                ["Monitor não liga"]),
    "Impressora": (["Feita mudança de cabo de força", "Testado em outra tomada"],
                   ["Impressora não liga"]),
    "Teclado": (["Testado em outra porta USB", "Testado em outro micro"],
                ["Teclado não funciona"]),
    "Mouse": (["Testado em outra porta USB", "Testado em outro micro"],
              ["Mouse não funciona"]),
    "Webcam": (["Testado em outra porta USB", "Testado em outro micro"],
               ["Webcam não é reconhecida"]),
    "Caixa de som": (["Testado em outra saída de áudio", "Testado em outro micro"],
                     ["Caixa de som sem áudio"]),
}

# Outros nomes que o técnico usa -> tipo do script.
_APELIDOS = {
    "maquina": "Computador", "micro": "Computador", "cpu": "Computador",
    "desktop": "Computador", "pc": "Computador", "computador": "Computador",
    "notebook": "Notebook", "note": "Notebook", "laptop": "Notebook",
    "monitor": "Monitor", "tela": "Monitor",
    "impressora": "Impressora", "multifuncional": "Impressora",
    "teclado": "Teclado", "mouse": "Mouse",
    "webcam": "Webcam", "camera": "Webcam",
    "caixa de som": "Caixa de som", "caixinha de som": "Caixa de som",
    "caixas de som": "Caixa de som", "som": "Caixa de som",
}


def _chave(s: str) -> str:
    t = unicodedata.normalize("NFD", (s or "").strip().lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def tipo_de(valor: str) -> str:
    """'máquina' -> 'Computador'; '' se não for um tipo do script."""
    k = _chave(valor)
    return _APELIDOS.get(k) or next((t for t in TIPOS if _chave(t) == k), "")


def tem_tombo(tipo: str) -> bool:
    return tipo in PRINCIPAIS


def modelos_de(tipo: str) -> list[conhecimento.ModeloDespacho]:
    """Os modelos de despacho do tipo (lidos a cada chamada: editar o .md
    vale na hora)."""
    return [m for m in conhecimento.despachos() if tipo_de(m.tipo) == tipo]


def achar_modelo(tipo: str, dito: str) -> list[conhecimento.ModeloDespacho]:
    """Os modelos do tipo que casam com o que foi dito (nome do modelo ou um
    dos `pedidos`). Um só = esse; vários = perguntar entre eles; nenhum =
    perguntar entre todos do tipo."""
    k = _chave(dito)
    modelos = modelos_de(tipo)
    if not k:
        return []
    exato = [m for m in modelos if _chave(m.nome) == k
             or _chave(m.nome.split("—")[-1]) == k]
    if exato:
        return exato
    return [m for m in modelos
            if k in _chave(m.nome)
            or any(p and (p in k or k in p)
                   for p in map(_chave, m.pedidos.split(",")))]


def itens(texto: "str | list[str]") -> list[str]:
    """Uma linha (ou item de lista) por teste/defeito, sem o '-' e o ';'."""
    linhas = texto if isinstance(texto, list) else str(texto or "").split("\n")
    return [l.strip().lstrip("-•").strip().rstrip(";.").strip()
            for l in linhas if str(l).strip().lstrip("-•").strip()]


# Uma linha do script = lista de pedaços (texto, estilo). Resposta sai em
# VERMELHO no Assyst, rótulo do campo em NEGRITO (pedido dele, 26/10), o resto
# em azul-marinho (padrão da auditoria); linha vazia = linha em branco. O
# texto puro (cartão) e o HTML (Assyst) saem da MESMA montagem, para nunca se
# desencontrarem.
TEXTO, ROTULO, RESPOSTA = "texto", "rotulo", "resposta"
Linha = list[tuple[str, str]]


def _marca(t: str, tipo: str) -> Linha:
    return [("(X)", RESPOSTA) if t == tipo else ("( )", TEXTO), (f" {t}", TEXTO)]


def _linhas(tipo: str, localizacao: str, marca: str, modelo: str, serie: str,
            testes: list[str], defeitos: list[str], tombo: str = "",
            obs: str = "") -> list[Linha]:
    """O script linha a linha. Mesma pontuação do modelo do CATI."""
    outro = tipo if tipo in OUTROS else ""
    linha_tipo: Linha = [("Tipo:", ROTULO), (" ", TEXTO)]
    for i, t in enumerate(PRINCIPAIS):
        linha_tipo += ([(" ", TEXTO)] if i else []) + _marca(t, tipo)
    linha_tipo += [(". ", TEXTO), ("(X)", RESPOSTA) if outro else ("( )", TEXTO),
                   (" Outros Qual? ", TEXTO),
                   (outro, RESPOSTA) if outro else ("________", TEXTO)]
    dados = [linha_tipo, []]  # linha em branco depois do Tipo (pedido dele, 26/10)
    if tem_tombo(tipo):
        dados.append([("Tombo do Computador:", ROTULO), (" ", TEXTO), (tombo, RESPOSTA)])
    dados += [[("Marca:", ROTULO), (" ", TEXTO), (marca.upper(), RESPOSTA)],
              [("Modelo:", ROTULO), (" ", TEXTO), (modelo, RESPOSTA)],
              [("N° de Série:", ROTULO), (" ", TEXTO), (serie, RESPOSTA)]]
    return [
        [("Chamado está sendo direcionado ao Serviço de Operações para realizar "
          "as medidas cabíveis:", TEXTO)],
        [],
        [("Localização do Equipamento:", ROTULO), (" ", TEXTO), (localizacao, RESPOSTA)],
        [],
        [("Dados do Equipamento:", ROTULO)],
        *dados,
        [],
        [("Obs:", ROTULO)] + ([(f" {obs}", RESPOSTA)] if obs else []),
        [],
        [("Testes realizado:", ROTULO)],
        *[[(f"- {t};", RESPOSTA)] for t in testes],
        [],
        [("Defeito apresentado:", ROTULO)],
        *[[(f"- {d};", RESPOSTA)] for d in defeitos],
    ]


def montar_texto(*args, **kwargs) -> str:
    """O script em texto puro (o que o cartão mostra)."""
    return "\n".join("".join(t for t, _ in ln) for ln in _linhas(*args, **kwargs))


def montar_html(*args, **kwargs) -> str:
    """O script formatado para o Assyst: azul-marinho, rótulos em negrito,
    respostas em vermelho."""
    from services.assyst.ckeditor_pw import AZUL_MARINHO, VERMELHO, paragrafo, trecho

    def _html(t: str, estilo: str) -> str:
        if estilo == RESPOSTA:
            return trecho(t, VERMELHO)
        if estilo == ROTULO:
            return f"<strong>{trecho(t, AZUL_MARINHO)}</strong>"
        return trecho(t, AZUL_MARINHO)

    return "".join(
        paragrafo(*(_html(t, e) for t, e in ln if t)) if ln else "<p>&nbsp;</p>"
        for ln in _linhas(*args, **kwargs))
