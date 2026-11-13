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

import re
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

# Marca e modelo PADRÃO dos periféricos (09/11, regra da equipe): o técnico
# só diz o serial. Webcam e caixa de som não têm padrão: ele diz.
PADRAO_PERIFERICO: dict[str, tuple[str, str]] = {
    "Mouse": ("Positivo", "SM-6620"),
    "Teclado": ("Positivo", "SK-6620"),
}

# Tipos cujo tombo é de uma máquina no Itom (marca, modelo e série vêm de lá).
NO_ITOM = ["Computador", "Notebook"]

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


def periferico(tipo: str) -> bool:
    """Teclado, mouse, webcam, caixa de som: sem tombo, ligados a um micro."""
    return tipo in OUTROS


# --------------------------------------------------------------------------- #
# Dados que saem do chamado e do Itom (09/11): o técnico só diz o defeito e,
# no periférico, o serial.
# --------------------------------------------------------------------------- #

# A seção vem do Assyst em maiúsculas e sem acento.
_ACENTOS = {
    "familia": "Família", "civel": "Cível", "civeis": "Cíveis", "publica": "Pública",
    "sucessoes": "Sucessões", "camara": "Câmara", "orfaos": "Órfãos",
    "execucao": "Execução", "execucoes": "Execuções", "penais": "Penais",
    "infancia": "Infância", "juventude": "Juventude", "transito": "Trânsito",
    "violencia": "Violência", "domestica": "Doméstica", "fazenda": "Fazenda",
    "secretaria": "Secretaria", "judiciaria": "Judiciária", "tecnologia": "Tecnologia",
    "informacao": "Informação", "comunicacao": "Comunicação", "gestao": "Gestão",
    "coordenadoria": "Coordenadoria", "diretoria": "Diretoria", "orgao": "Órgão",
    "especial": "Especial", "especiais": "Especiais", "unica": "Única",
}
_MINUSCULAS = {"da", "de", "do", "das", "dos", "e", "em", "na", "no", "a", "o"}
_SIGLAS = {"JECC", "JEC", "JECRIM", "CEJUSC", "CATI", "TJCE", "TI", "NUPEMEC", "ESMEC"}


def secao_legivel(secao: str) -> str:
    """'15ª VARA DE FAMILIA DA COMARCA DE FORTALEZA' -> '15ª Vara de Família'.
    Fortaleza é a comarca da maioria: some. As outras ficam ('da Comarca de Sobral')."""
    s = " ".join((secao or "").split())
    s = re.sub(r"\s+DA COMARCA DE FORTALEZA$", "", s, flags=re.I)
    palavras = []
    for i, p in enumerate(s.split(" ")):
        k = _chave(p)
        if p[:1].isdigit():
            palavras.append(p.lower())                     # 15ª, 1º
        elif k in _ACENTOS:
            palavras.append(_ACENTOS[k])
        elif i and k in _MINUSCULAS:
            palavras.append(k)
        elif k.upper() in _SIGLAS:
            palavras.append(k.upper())
        else:
            palavras.append(p[:1].upper() + p[1:].lower())
    return " ".join(palavras)


# "Secretaria da 3ª Vara..., setor verde, nível 1, sala 103." (13/11): a
# localidade escrita solta na descrição, sem "Local:". Só os pedaços de onde é
# (nível, setor, sala, andar) entram; o resto da frase repetiria a seção.
_PEDACOS_LOCAL = (
    ("Nível", r"n[ií]vel\s*[:\-]?\s*([^,.;\n]{1,20})"),
    ("Setor", r"setor\s*[:\-]?\s*([^,.;\n]{1,25})"),
    ("Sala", r"sala\s*(?:n[º°o.]*\s*)?[:\-]?\s*([^,.;\n]{1,25})"),
    ("Andar", r"(\d+)\s*[º°o]?\s*andar\b"),
)


def _palavras_local(valor: str) -> str:
    # Corta no próximo pedaço ("azul - Sala 214") e no "da 2ª vara" do fim.
    valor = re.split(r"\s+[-–]\s*|\s(?=(?:n[ií]vel|setor|sala)\b)", valor, flags=re.I)[0]
    valor = re.sub(r"\s+d[aoe]s?\s+\d.*$", "", valor)
    out = []
    for i, p in enumerate(valor.split()[:4]):
        k = _chave(p)
        out.append(k if k in _MINUSCULAS else
                   p if p[:1].isdigit() else p[:1].upper() + p[1:].lower())
    return " ".join(out)


def local_na_descricao(texto: str) -> str:
    """'..., setor verde, nível 1, sala 103.' -> 'Nível 1, Setor Verde, Sala 103'.
    Lê a 1ª linha que tenha sala/nível/setor/andar. '' = nenhuma."""
    for linha in (texto or "").splitlines():
        achados = {}
        for rotulo, rx in _PEDACOS_LOCAL:
            m = re.search(r"\b" + rx, linha, re.I)
            if m and m[1].strip():
                achados[rotulo] = m[1].strip()
        if not achados:
            continue
        partes = [f"{r} {_palavras_local(achados[r])}"
                  for r in ("Nível", "Setor", "Sala") if r in achados]
        if "Andar" in achados:
            partes.insert(0, f"{achados['Andar']}º Andar")
        return ", ".join(partes)
    return ""


def localizacao(secao: str, sala: str = "", local_descrito: str = "",
                edificio: str = "") -> str:
    """'15ª Vara de Família, Nível 2, Setor Verde, Sala 314' (formato da equipe,
    09/11). Onde é: o 'Local:' da descrição, senão o campo Sala; sem nenhum
    dos dois, o edifício. '' = nada no chamado (o técnico diz)."""
    onde = (local_descrito or "").strip()
    if not onde:
        s = (sala or "").strip()
        if s and "definir" not in s.lower():
            onde = s if re.search(r"[a-zA-Z]", s) else f"Sala {s}"
    if not onde and edificio and "definir" not in edificio.lower():
        onde = edificio.strip()
    partes = [x for x in (secao_legivel(secao), onde) if x]
    return ", ".join(partes) if onde else ""


def separar_marca_modelo(marca_modelo: str) -> tuple[str, str]:
    """'POSITIVO C6200' (Itom, aba Hardware) -> ('POSITIVO', 'C6200')."""
    partes = (marca_modelo or "").split(maxsplit=1)
    return (partes[0], partes[1]) if len(partes) == 2 else ((partes[0], "") if partes else ("", ""))


def vinculo_do_periferico(tombo_micro: str, marca_modelo: str = "") -> str:
    """A OBS do periférico: 'O periférico está vinculado ao micro Positivo
    C6200 de tombo 654321.' (texto da equipe, 09/11)."""
    marca, modelo = separar_marca_modelo(marca_modelo)
    micro = " ".join(x for x in (marca[:1].upper() + marca[1:].lower(), modelo) if x)
    return (f"O periférico está vinculado ao micro {micro} de tombo {tombo_micro}."
            if micro else f"O periférico está vinculado ao micro de tombo {tombo_micro}.")


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
