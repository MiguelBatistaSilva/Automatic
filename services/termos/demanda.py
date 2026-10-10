"""
services/termos/demanda.py — Termo da TAREFA DE DEMANDA (eventos), 10/10.

"Comprovação de prestação de serviço referente a Tarefa de Demanda": o
técnico leva ao evento, o validador assina, e o PDF vai anexado ao chamado.

Visual = o modelo que o CATI já usa (brasão, Liberation Serif, tabela de
duas colunas), não o do termo de troca de máquina — pedido dele.

De onde vem cada campo (ver memória/README do domínio termos):
  - solicitante = requisitante = usuário afetado do chamado;
  - local e descrição do evento = DESCRIÇÃO do chamado (texto livre),
    extraídos AQUI pelo código — a descrição nunca vai para a IA: no fim
    dela vem colado um bloco com CPF, telefone e nascimento do solicitante;
  - data e horas estimadas = Início/Fim agendado;
  - data do serviço = data estimada; horas de execução = as do evento real
    (o técnico informa; sem isso, as agendadas);
  - validador, OBS = o técnico; técnico = cabeçalho do Assyst + credenciais.
"""

import dataclasses
import datetime
import pathlib
import re

from services.termos.modelo import Pessoa
from services.termos.odt import _NS, _p, _txt, escrever_odt

_RECURSOS = pathlib.Path(__file__).parent / "recursos"
_MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
          "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


@dataclasses.dataclass
class TermoDemanda:
    chamado: str = ""
    solicitante: str = ""
    requisitante: str = ""          # vazio = o solicitante
    local: str = ""
    data: "datetime.date | None" = None   # estimada = do serviço
    inicio_previsto: str = ""       # hh:mm (Início agendado)
    fim_previsto: str = ""          # hh:mm (Fim agendado)
    descricao: str = ""
    validador: Pessoa = dataclasses.field(default_factory=Pessoa)
    inicio: str = ""                # hh:mm da execução (vazio = previsto)
    fim: str = ""
    tecnico: Pessoa = dataclasses.field(default_factory=Pessoa)
    obs: str = ""

    titulo = "Comprovação de prestação de serviço referente a Tarefa de Demanda"


# --------------------------------------------------------------------------- #
# Leitura da descrição do chamado (texto livre) — pelo CÓDIGO, nunca pela IA
# --------------------------------------------------------------------------- #

_ENDERECO = re.compile(r"^(rua|r\.|av\.?|avenida|travessa|tv\.?|rodovia|estrada|"
                       r"alameda|pra[cç]a|via)\b", re.I)
_SAUDACAO = re.compile(r"^(bom dia|boa tarde|boa noite|ol[aá]|prezad|car[oa]s?\b|senhor)",
                       re.I)


def _linhas(texto: str) -> list[str]:
    return [l.replace("\xa0", " ").strip() for l in (texto or "").splitlines()]


def extrair_local(descricao: str) -> str:
    """'Local: Esmec' + a linha seguinte, se for endereço ('Rua ...').
    Rótulo sozinho na linha ('Local:') = o valor está na linha de baixo."""
    linhas = _linhas(descricao)
    for i, l in enumerate(linhas):
        m = re.match(r"(?:local|endere[cç]o)(?:\s+do evento)?\s*[:\-–]\s*(.*)$", l, re.I)
        if not m:
            continue
        resto = [x for x in linhas[i + 1:i + 3] if x]
        local = m[1].strip() or (resto.pop(0) if resto else "")
        if resto and _ENDERECO.match(resto[0]):
            local = f"{local} — {resto[0]}" if local else resto[0]
        return re.sub(r"\s+", " ", local)
    return ""


def extrair_descricao(descricao: str, limite: int = 600) -> str:
    """O 1º parágrafo de verdade do pedido ('Solicitamos profissional...'),
    pulando saudação. Parágrafos = blocos separados por linha em branco."""
    blocos, atual = [], []
    for l in _linhas(descricao) + [""]:
        if l:
            atual.append(l)
        elif atual:
            blocos.append(" ".join(atual))
            atual = []
    for i, b in enumerate(blocos):
        b = re.sub(r"\s+", " ", b).strip()
        if len(b) < 25 or _SAUDACAO.match(b) and len(b) < 60:
            continue
        # "Solicitamos profissional da CATI para:" + a lista no bloco de
        # baixo (visto no S2440121, 10/10): o que vem depois dos dois-pontos
        # é o próprio pedido — junta até fechar a frase.
        for seguinte in blocos[i + 1:]:
            if not b.endswith(":") or len(b) >= limite:
                break
            continuacao = re.sub(r"\s+", " ", seguinte).strip()
            b = f"{b} {continuacao}"
        return b if len(b) <= limite else b[:limite - 1].rstrip() + "…"
    return ""


_PARTICULAS = {"da", "das", "de", "do", "dos", "e"}


def nome_proprio(nome: str) -> str:
    """'FRANCISCO JOSE ROSA DOS SANTOS' -> 'Francisco Jose Rosa dos Santos'
    (o Assyst guarda em maiúsculas; o termo usa nome próprio)."""
    partes = (nome or "").strip().split()
    return " ".join(p.lower() if i and p.lower() in _PARTICULAS else p.capitalize()
                    for i, p in enumerate(partes))


# --------------------------------------------------------------------------- #
# Documento
# --------------------------------------------------------------------------- #

_TAB = [5.556, 11.439]  # larguras do modelo original (cm)


def _rotulo(texto: str) -> str:
    """Nome do campo em negrito; o valor ao lado fica normal (pedido de 10/10)."""
    return f'<text:span text:style-name="D_Rotulo">{_txt(texto)}</text:span>'


def _linha_info(rotulo: str, valor: str) -> str:
    return _p("D_Info", f"{_rotulo(rotulo + ':')} {_txt(valor)}")


def _content(t: TermoDemanda) -> str:
    data = t.data.strftime("%d/%m/%Y") if t.data else ""
    brasao = (
        '<draw:frame draw:style-name="Brasao" draw:name="Brasao" text:anchor-type="as-char" '
        'svg:width="1.663cm" svg:height="1.725cm" draw:z-index="0">'
        '<draw:image xlink:href="Pictures/brasao_ce.emf" xlink:type="simple" xlink:show="embed" '
        'xlink:actuate="onLoad" draw:mime-type="image/x-emf"/>'
        '<draw:image xlink:href="Pictures/brasao_ce.png" xlink:type="simple" xlink:show="embed" '
        'xlink:actuate="onLoad" draw:mime-type="image/png"/></draw:frame>')

    def linha(rotulo: str, valor: str) -> str:
        return ('<table:table-row table:style-name="DLinha">'
                f'<table:table-cell table:style-name="DCel" office:value-type="string">'
                f'{_p("D_CelulaRotulo", _txt(rotulo))}</table:table-cell>'
                f'<table:table-cell table:style-name="DCel" office:value-type="string">'
                f'{_p("D_Celula", _txt(valor))}</table:table-cell></table:table-row>')

    tabela = (
        '<table:table table:name="OrdemServico" table:style-name="DTab">'
        '<table:table-column table:style-name="DColA"/><table:table-column table:style-name="DColB"/>'
        '<table:table-row><table:table-cell table:style-name="DCel" '
        'table:number-columns-spanned="2" office:value-type="string">'
        + _p("D_TabTitulo", "TAREFA DE DEMANDA – Ordem de serviço")
        + '</table:table-cell><table:covered-table-cell/></table:table-row>'
        + linha("Usuário Validador", t.validador.nome)
        + linha("Matrícula do Validador", t.validador.matricula)
        + linha("Data do serviço (execução)", data)
        + linha("Hora de início (execução)", t.inicio or t.inicio_previsto)
        + linha("Hora de término (execução)", t.fim or t.fim_previsto)
        + linha("Chamado Assyst/CPA", t.chamado)
        + linha("Nome do Técnico", t.tecnico.nome)
        + linha("Matrícula do Técnico", t.tecnico.matricula)
        + "</table:table>")
    obs = _rotulo("OBS:") + (
        f' <text:span text:style-name="D_Sublinhado">{_txt(t.obs)}</text:span>'
        if t.obs else " " + "_" * 70)
    quando = (f"Fortaleza, {t.data:%d} de {_MESES[t.data.month - 1]} de {t.data:%Y}."
              if t.data else "Fortaleza, ____ de ______________ de ______.")
    corpo = "".join([
        _p("D_Centro", brasao),
        *(_p("D_Orgao", x) for x in ("ESTADO DO CEARÁ", "PODER JUDICIÁRIO",
                                      "TRIBUNAL DE JUSTIÇA",
                                      "SECRETARIA DE TECNOLOGIA DA INFORMAÇÃO")),
        _p("D_Corpo"), _p("D_Corpo"),
        _p("D_Titulo", _txt(t.titulo)),
        _p("D_Info"),
        _linha_info("Solicitante", t.solicitante),
        _linha_info("Requisitante", t.requisitante or t.solicitante),
        _linha_info("Local/Endereço do evento", t.local),
        _linha_info("Data estimada do serviço", data),
        _linha_info("Hora estimada de início", t.inicio_previsto),
        _linha_info("Hora estimada de término", t.fim_previsto),
        _linha_info("Descrição do evento", t.descricao),
        _p("D_Info"),
        tabela,
        _p("D_Corpo"), _p("D_Corpo"),
        _p("D_Corpo", obs),
        _p("D_Corpo"),
        _p("D_Corpo", "Confirmo que o técnico compareceu na data e horário informados acima."),
        _p("D_Corpo"),
        _p("D_Corpo", _txt(quando)),
        # Espaço para assinar num estilo (não em linhas vazias) e a linha
        # PRESA à legenda: nunca cai uma sem a outra na página seguinte.
        _p("D_Assinatura", "_" * 57),
        _p("D_Centro", "Assinatura do Validador"),
    ])
    cel = 'fo:padding="0.097cm" fo:border="0.05pt solid #000000"'
    automaticos = (
        '<style:style style:name="DTab" style:family="table">'
        f'<style:table-properties style:width="{sum(_TAB):.3f}cm" table:align="left" '
        'style:may-break-between-rows="false"/></style:style>'
        f'<style:style style:name="DColA" style:family="table-column">'
        f'<style:table-column-properties style:column-width="{_TAB[0]}cm"/></style:style>'
        f'<style:style style:name="DColB" style:family="table-column">'
        f'<style:table-column-properties style:column-width="{_TAB[1]}cm"/></style:style>'
        f'<style:style style:name="DCel" style:family="table-cell">'
        f'<style:table-cell-properties {cel}/></style:style>'
        '<style:style style:name="DLinha" style:family="table-row">'
        '<style:table-row-properties style:min-row-height="0.727cm"/></style:style>'
        '<style:style style:name="Brasao" style:family="graphic">'
        '<style:graphic-properties style:vertical-pos="top" style:vertical-rel="baseline" '
        'fo:border="none" fo:padding="0cm"/></style:style>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<office:document-content {_NS}>'
        '<office:font-face-decls><style:font-face style:name="Liberation Serif" '
        "svg:font-family=\"'Liberation Serif'\" style:font-family-generic=\"roman\"/>"
        '</office:font-face-decls>'
        f'<office:automatic-styles>{automaticos}</office:automatic-styles>'
        f'<office:body><office:text>{corpo}</office:text></office:body>'
        '</office:document-content>'
    )


def _par(nome: str, par: str = "", txt: str = "") -> str:
    return (f'<style:style style:name="{nome}" style:display-name="{nome.replace("_", " ")}" '
            'style:family="paragraph" style:parent-style-name="Standard">'
            f'<style:paragraph-properties {par}/><style:text-properties {txt}/></style:style>')


def _styles() -> str:
    """Estilos COM NOME (D_...): o mesmo visual do modelo original — texto
    12 pt, linhas de informação 13 pt, título sublinhado."""
    centro = 'fo:text-align="center"'
    nomeados = (
        '<style:default-style style:family="paragraph">'
        '<style:text-properties style:font-name="Liberation Serif" fo:font-size="12pt" '
        'fo:language="pt" fo:country="BR"/></style:default-style>'
        '<style:style style:name="Standard" style:family="paragraph" style:class="text"/>'
        + _par("D_Centro", centro)
        + _par("D_Orgao", centro, 'fo:font-weight="bold"')
        + _par("D_Assinatura", centro + ' fo:margin-top="2.2cm" fo:keep-with-next="always"')
        + _par("D_Titulo", centro,
               'fo:font-weight="bold" style:text-underline-style="solid" '
               'style:text-underline-width="auto" style:text-underline-color="font-color"')
        + _par("D_Info", 'fo:text-align="justify"', 'fo:font-size="13pt"')
        + _par("D_Corpo", 'fo:text-align="justify"')
        + _par("D_Celula", "")
        + _par("D_CelulaRotulo", "", 'fo:font-weight="bold"')
        + _par("D_TabTitulo", centro, 'fo:font-weight="bold"')
        + '<style:style style:name="D_Rotulo" style:display-name="D Rotulo" '
          'style:family="text"><style:text-properties fo:font-weight="bold"/></style:style>'
        + '<style:style style:name="D_Sublinhado" style:display-name="D Sublinhado" '
          'style:family="text"><style:text-properties style:text-underline-style="solid" '
          'style:text-underline-width="auto" style:text-underline-color="font-color"/></style:style>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<office:document-styles {_NS}>'
        '<office:font-face-decls><style:font-face style:name="Liberation Serif" '
        "svg:font-family=\"'Liberation Serif'\" style:font-family-generic=\"roman\"/>"
        '</office:font-face-decls>'
        f'<office:styles>{nomeados}</office:styles>'
        '<office:automatic-styles><style:page-layout style:name="Pagina">'
        '<style:page-layout-properties fo:page-width="21cm" fo:page-height="29.7cm" '
        'style:print-orientation="portrait" fo:margin-top="2cm" fo:margin-bottom="2cm" '
        'fo:margin-left="2cm" fo:margin-right="2cm"/></style:page-layout>'
        '</office:automatic-styles>'
        '<office:master-styles><style:master-page style:name="Standard" '
        'style:page-layout-name="Pagina"/></office:master-styles>'
        '</office:document-styles>'
    )


def gerar_odt(termo: TermoDemanda, destino: "str | pathlib.Path") -> pathlib.Path:
    return escrever_odt(destino, _content(termo), _styles(), termo.titulo, {
        "brasao_ce.emf": _RECURSOS / "brasao_ce.emf",
        "brasao_ce.png": _RECURSOS / "brasao_ce.png",
    })
