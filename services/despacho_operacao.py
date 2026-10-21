"""
services/despacho_operacao.py — Script de DESPACHO de equipamento ao Serviço
de Operações (20/10).

"Preciso condenar um teclado..." / "mandar a máquina ... para a Operação": o
chamado vai PAUSADO pela mesma ação 'Aguardando Info do Fornecedor', só que
com este script no lugar do texto livre. Aqui só se MONTA o texto; quem
escreve no Assyst é o fluxo de sempre (services/flow_fornecedor_pw.py).

Testes e defeito são obrigatórios: se o técnico não disser, vale o script
PRONTO do tipo (SCRIPTS abaixo — edite aqui para mudar o padrão).
Teclado, mouse, webcam e caixa de som não têm tombo: a linha nem sai.
"""

import unicodedata

# Tipos da linha "Tipo:" do script, na ordem em que aparecem.
PRINCIPAIS = ["Computador", "Notebook", "Monitor", "Impressora"]
# Os que vão em "( ) Outros Qual?".
OUTROS = ["Teclado", "Mouse", "Webcam", "Caixa de som"]
TIPOS = PRINCIPAIS + OUTROS

# Script pronto por tipo: (testes realizados, defeito apresentado).
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


def itens(texto: "str | list[str]") -> list[str]:
    """Uma linha (ou item de lista) por teste/defeito, sem o '-' e o ';'."""
    linhas = texto if isinstance(texto, list) else str(texto or "").split("\n")
    return [l.strip().lstrip("-•").strip().rstrip(";.").strip()
            for l in linhas if str(l).strip().lstrip("-•").strip()]


def _marca(t: str, tipo: str) -> str:
    return f"({'X' if t == tipo else ' '}) {t}"


def montar_texto(tipo: str, localizacao: str, marca: str, modelo: str,
                 serie: str, testes: list[str], defeitos: list[str],
                 tombo: str = "", obs: str = "") -> str:
    """O script, linha a linha (o fluxo pinta de azul-marinho e cada linha
    vira um parágrafo). Mesma pontuação do modelo do CATI."""
    outro = tipo if tipo in OUTROS else ""
    linha_tipo = ("Tipo: " + " ".join(_marca(t, tipo) for t in PRINCIPAIS[:-1])
                  + f" {_marca(PRINCIPAIS[-1], tipo)}. "
                  + f"({'X' if outro else ' '}) Outros Qual? {outro or '________'}")
    dados = [linha_tipo]
    if tem_tombo(tipo):
        dados.append(f"Tombo do Computador: {tombo}")
    dados += [f"Marca: {marca.upper()}", f"Modelo: {modelo}", f"N° de Série: {serie}"]
    return "\n".join([
        "Chamado está sendo direcionado ao Serviço de Operações para realizar "
        "as medidas cabíveis:",
        "",
        f"Localização do Equipamento: {localizacao}",
        "",
        "Dados do Equipamento:",
        *dados,
        "",
        f"Obs: {obs}".rstrip(),
        "",
        "Testes realizado:",
        *[f"- {t};" for t in testes],
        "",
        "Defeito apresentado:",
        *[f"- {d};" for d in defeitos],
    ])
