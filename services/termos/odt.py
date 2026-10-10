"""
services/termos/odt.py — Monta o .odt (LibreOffice Writer) do Termo (10/10).

Sem biblioteca: um .odt é um zip com XML. A APARÊNCIA mora em styles.xml,
em estilos COM NOME ("Termo_Titulo", "Termo_Secao"...) — dá para ajustar
no próprio Writer (F11 → Estilos) e trazer os valores de volta para cá.
O content.xml só monta a estrutura e usa esses nomes.

Cabeçalho (logo + órgão) e rodapé (chamado + página) ficam na página-mestre:
repetem sozinhos quando o termo de várias máquinas passa de uma página.
"""

import pathlib
import re
import shutil
import subprocess
import zipfile
from xml.sax.saxutils import escape

from services.termos.modelo import Equipamento, Pessoa, Termo, Troca
from services.termos.textos import Trecho, declaracoes

LOGO = pathlib.Path(__file__).parent / "recursos" / "logo_tjce.png"
_LOGO_PX = (461, 190)

# Monocromático (10/10): o termo é impresso, quase sempre em preto e branco.
# A única cor é a do logo.
DESTAQUE = "#1A1A1A"         # títulos e seções
FILETE = "#1A1A1A"         # filetes (cabeçalho e seções)
TINTA = "#1A1A1A"
CINZA = "#595959"
FUNDO_ROTULO = "#F2F2F2"
FUNDO_CABECALHO = "#D9D9D9"
BORDA = "0.5pt solid #8C8C8C"
# Linha mais grossa separando uma máquina da outra na tabela.
BORDA_GRUPO = "1.25pt solid #1A1A1A"

LARGURA = 17.0  # cm úteis (A4 com 2 cm de cada lado)

_NS = (
    'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
    'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
    'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
    'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
    'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" '
    'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" '
    'xmlns:xlink="http://www.w3.org/1999/xlink" '
    'xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0" '
    'xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0" '
    'office:version="1.3"'
)


# --------------------------------------------------------------------------- #
# Texto
# --------------------------------------------------------------------------- #

def _txt(s: str) -> str:
    """Escapa e preserva espaços repetidos e quebras de linha (no ODF, vários
    espaços seguidos viram um só)."""
    s = escape(s or "")
    s = re.sub(r" {2,}", lambda m: f' <text:s text:c="{len(m[0]) - 1}"/>', s)
    return s.replace("\n", "<text:line-break/>")


def _p(estilo: str, conteudo: str = "") -> str:
    return f'<text:p text:style-name="{estilo}">{conteudo}</text:p>'


def _trechos(trechos: list[Trecho]) -> str:
    return "".join(
        f'<text:span text:style-name="Termo_Destaque">{_txt(t)}</text:span>' if negrito
        else _txt(t) for t, negrito in trechos)


# --------------------------------------------------------------------------- #
# Tabelas
# --------------------------------------------------------------------------- #

class _Cel:
    def __init__(self, conteudo: str, estilo_cel: str, estilo_p: str, span: int = 1):
        self.conteudo, self.estilo_cel, self.estilo_p, self.span = \
            conteudo, estilo_cel, estilo_p, span


def _rot(texto: str, span: int = 1, grupo: bool = False) -> _Cel:
    """`grupo` = 1ª linha de uma máquina: ganha o filete grosso em cima."""
    return _Cel(_txt(texto), "CelRotuloGrupo" if grupo else "CelRotulo",
                "Termo_Rotulo", span)


def _val(texto: str, span: int = 1, grupo: bool = False) -> _Cel:
    return _Cel(_txt(texto), "CelValorGrupo" if grupo else "CelValor",
                "Termo_Valor", span)


def _cab(texto: str, span: int = 1) -> _Cel:
    return _Cel(_txt(texto), "CelCabecalho", "Termo_ColCab", span)


class _Tabelas:
    """Gera as tabelas do content.xml e junta os estilos automáticos de
    coluna que elas precisam (um por largura)."""

    def __init__(self):
        self.larguras: set[float] = set()
        self.n = 0

    def tabela(self, larguras: list[float], linhas: list[tuple[str, list[_Cel]]],
               inteira: bool = False, cabecalho: int = 0) -> str:
        """`linhas`: (estilo da linha, células). `inteira` = não quebra a
        tabela entre páginas. `cabecalho` = quantas linhas do topo se repetem
        em cada página quando a tabela quebra."""
        self.n += 1
        self.larguras.update(larguras)
        cols = "".join(f'<table:table-column table:style-name="{_col(w)}"/>'
                       for w in larguras)
        corpo = []
        for estilo_linha, cels in linhas:
            partes = []
            for c in cels:
                span = f' table:number-columns-spanned="{c.span}"' if c.span > 1 else ""
                partes.append(
                    f'<table:table-cell table:style-name="{c.estilo_cel}"{span} '
                    f'office:value-type="string">{_p(c.estilo_p, c.conteudo)}'
                    '</table:table-cell>'
                    + "<table:covered-table-cell/>" * (c.span - 1))
            corpo.append(f'<table:table-row table:style-name="{estilo_linha}">'
                         + "".join(partes) + "</table:table-row>")
        if cabecalho:
            corpo = (["<table:table-header-rows>"] + corpo[:cabecalho]
                     + ["</table:table-header-rows>"] + corpo[cabecalho:])
        estilo = "TabInteira" if inteira else "Tab"
        return (f'<table:table table:name="Tabela{self.n}" table:style-name="{estilo}">'
                + cols + "".join(corpo) + "</table:table>")

    def estilos(self) -> str:
        return "".join(
            f'<style:style style:name="{_col(w)}" style:family="table-column">'
            f'<style:table-column-properties style:column-width="{w}cm"/></style:style>'
            for w in sorted(self.larguras))


def _col(w: float) -> str:
    return f"Col{int(round(w * 100))}"


# --------------------------------------------------------------------------- #
# Blocos do termo
# --------------------------------------------------------------------------- #

def _secao(titulo: str) -> str:
    return _p("Termo_Secao", _txt(titulo))


def _bloco_atendimento(t: Termo, tab: _Tabelas) -> str:
    data = t.data.strftime("%d/%m/%Y") if t.data else ""
    return _secao("Dados do atendimento") + tab.tabela([3.6, 5.9, 2.0, 5.5], [
        ("Linha", [_rot("Unidade judiciária ou administrativa"), _val(t.unidade, 3)]),
        ("Linha", [_rot("Chamado Assyst"), _val(t.chamado), _rot("Data"), _val(data)]),
    ])


_CAMPOS = [
    ("Marca / modelo", lambda e: e.marca_modelo),
    ("Tombo", lambda e: e.tombo),
    ("Nº de série", lambda e: e.serie),
    ("Hostname", lambda e: e.hostname),
]


def _bloco_equipamentos(t: Termo, tab: _Tabelas) -> str:
    """TODAS as máquinas numa tabela só (10/10): o cabeçalho Desinstalada /
    Instalada aparece uma vez (e se repete se a tabela virar a página) e um
    filete grosso separa uma máquina da outra — sem título por máquina."""
    linhas = [("Linha", [_cab(""), _cab("Desinstalada"), _cab("Instalada")])]
    for n, troca in enumerate(t.trocas or [Troca()]):
        for k, (rotulo, campo) in enumerate(_CAMPOS):
            grupo = n > 0 and k == 0
            linhas.append(("Linha", [_rot(rotulo, grupo=grupo),
                                     _val(campo(troca.desinstalada), grupo=grupo),
                                     _val(campo(troca.instalada), grupo=grupo)]))
    titulo = "Estações de trabalho" if t.varias else "Estação de trabalho"
    return _secao(titulo) + tab.tabela([3.6, 6.7, 6.7], linhas, cabecalho=1)


def _bloco_declaracoes(t: Termo) -> str:
    # Letra pequena (7 pt) nos dois layouts: o que o técnico confere são as
    # máquinas; o texto é padrão (pedido de 10/10).
    return _secao("Declarações") + "".join(
        _p("Termo_Declaracao", _trechos(par))
        for par in declaracoes(t.backup, t.varias, t.trava))


def _marcado(v: "bool | None", alvo: bool) -> str:
    return "( X )" if v is alvo else "(    )"


def _bloco_complemento(t: Termo, tab: _Tabelas) -> str:
    linhas = []
    if t.backup:
        linhas.append(("Linha", [
            _rot("Foi oferecido backup pelo OneDrive?"),
            _val(f"{_marcado(t.onedrive, True)} Sim      {_marcado(t.onedrive, False)} Não", 3)]))
    linhas.append(("LinhaAlta", [_rot("Observações"), _val(t.observacoes, 3)]))
    return tab.tabela([3.6, 5.9, 2.0, 5.5], linhas)


def _bloco_assinatura(p: Pessoa, tab: _Tabelas) -> str:
    """Nome / matrícula / assinatura de quem acompanhou — UMA vez por termo,
    no fim, valendo para todas as máquinas."""
    return _secao("Magistrado(a) ou servidor(a) que acompanhou o serviço") + tab.tabela(
        [3.6, 5.9, 2.0, 5.5], [
            ("Linha", [_rot("Nome"), _val(p.nome), _rot("Matrícula"), _val(p.matricula)]),
            ("LinhaAssinatura", [_rot("Assinatura e carimbo (caso possua)"), _val("", 3)]),
        ], inteira=True)


def _corpo(t: Termo, tab: _Tabelas) -> str:
    partes = [_p("Termo_Titulo", _txt(t.titulo)),
              _p("Termo_Subtitulo", _txt(t.subtitulo)),
              _bloco_atendimento(t, tab)]
    if not t.varias:
        partes += [
            _secao("Usuário recebedor do serviço"),
            tab.tabela([3.6, 5.9, 2.0, 5.5], [("Linha", [
                _rot("Nome completo"), _val(t.recebedor.nome),
                _rot("Matrícula"), _val(t.recebedor.matricula)])]),
            _bloco_equipamentos(t, tab),
            _bloco_declaracoes(t),
            _bloco_complemento(t, tab),
        ]
    else:
        partes.append(_bloco_equipamentos(t, tab))
        partes.append(_bloco_declaracoes(t))
        if t.backup or t.observacoes:
            partes.append(_bloco_complemento(t, tab))
    partes.append(_bloco_assinatura(t.recebedor, tab))
    return "".join(partes)


# --------------------------------------------------------------------------- #
# XML do pacote
# --------------------------------------------------------------------------- #

def _content(t: Termo) -> str:
    tab = _Tabelas()
    corpo = _corpo(t, tab)
    cel = (f'fo:padding-left="0.12cm" fo:padding-right="0.12cm" '
           f'fo:padding-top="0.03cm" fo:padding-bottom="0.03cm" fo:border="{BORDA}" '
           'style:vertical-align="middle"')
    automaticos = (
        '<style:style style:name="Tab" style:family="table">'
        f'<style:table-properties style:width="{LARGURA}cm" table:align="margins" '
        'fo:margin-top="0cm" fo:margin-bottom="0.15cm"/></style:style>'
        '<style:style style:name="TabInteira" style:family="table">'
        f'<style:table-properties style:width="{LARGURA}cm" table:align="margins" '
        'fo:margin-top="0cm" fo:margin-bottom="0.15cm" '
        'style:may-break-between-rows="false"/></style:style>'
        + tab.estilos() +
        '<style:style style:name="Linha" style:family="table-row">'
        '<style:table-row-properties style:min-row-height="0.52cm"/></style:style>'
        '<style:style style:name="LinhaAlta" style:family="table-row">'
        '<style:table-row-properties style:min-row-height="1.4cm"/></style:style>'
        '<style:style style:name="LinhaAssinatura" style:family="table-row">'
        '<style:table-row-properties style:min-row-height="1.3cm"/></style:style>'
        f'<style:style style:name="CelRotulo" style:family="table-cell">'
        f'<style:table-cell-properties {cel} fo:background-color="{FUNDO_ROTULO}"/></style:style>'
        f'<style:style style:name="CelValor" style:family="table-cell">'
        f'<style:table-cell-properties {cel}/></style:style>'
        f'<style:style style:name="CelRotuloGrupo" style:family="table-cell">'
        f'<style:table-cell-properties {cel} fo:border-top="{BORDA_GRUPO}" '
        f'fo:background-color="{FUNDO_ROTULO}"/></style:style>'
        f'<style:style style:name="CelValorGrupo" style:family="table-cell">'
        f'<style:table-cell-properties {cel} fo:border-top="{BORDA_GRUPO}"/></style:style>'
        f'<style:style style:name="CelCabecalho" style:family="table-cell">'
        f'<style:table-cell-properties {cel} fo:background-color="{FUNDO_CABECALHO}"/></style:style>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<office:document-content {_NS}>'
        '<office:font-face-decls><style:font-face style:name="Arial" '
        'svg:font-family="Arial" style:font-family-generic="swiss"/></office:font-face-decls>'
        f'<office:automatic-styles>{automaticos}</office:automatic-styles>'
        f'<office:body><office:text>{corpo}</office:text></office:body>'
        '</office:document-content>'
    )


def _par(nome: str, par: str = "", txt: str = "", pai: str = "Standard",
         proximo: str = "") -> str:
    prox = f' style:next-style-name="{proximo}"' if proximo else ""
    return (f'<style:style style:name="{nome}" style:display-name="{nome.replace("_", " ")}" '
            f'style:family="paragraph" style:parent-style-name="{pai}"{prox}>'
            f'<style:paragraph-properties {par}/><style:text-properties {txt}/></style:style>')


def _styles(t: Termo) -> str:
    alto = round(4.2 * _LOGO_PX[1] / _LOGO_PX[0], 3)
    nomeados = (
        '<style:default-style style:family="paragraph">'
        '<style:paragraph-properties fo:margin-top="0cm" fo:margin-bottom="0cm"/>'
        f'<style:text-properties style:font-name="Arial" fo:font-size="9.5pt" '
        f'fo:color="{TINTA}" fo:language="pt" fo:country="BR"/></style:default-style>'
        '<style:style style:name="Standard" style:family="paragraph" style:class="text"/>'
        # Cabeçalho / rodapé
        + _par("Termo_Cab_Estado", 'fo:text-align="end"',
               f'fo:font-size="7pt" fo:color="{CINZA}" fo:letter-spacing="0.03cm" '
               'fo:text-transform="uppercase"')
        + _par("Termo_Cab_Orgao", 'fo:text-align="end" fo:margin-top="0.04cm"',
               f'fo:font-size="9.5pt" fo:font-weight="bold" fo:color="{DESTAQUE}"')
        + _par("Termo_Cab_Depto", 'fo:text-align="end"',
               f'fo:font-size="8.5pt" fo:color="{CINZA}"')
        + _par("Termo_Filete",
               f'fo:border-bottom="1.5pt solid {FILETE}" fo:padding="0cm" fo:margin-top="0.1cm"',
               'fo:font-size="2pt"')
        + _par("Termo_Rodape",
               'fo:text-align="center" fo:border-top="0.5pt solid #C9D1DE" '
               'fo:padding-top="0.12cm"', f'fo:font-size="7.5pt" fo:color="{CINZA}"')
        # Corpo
        + _par("Termo_Titulo", 'fo:text-align="center" fo:margin-top="0.2cm"',
               f'fo:font-size="14pt" fo:font-weight="bold" fo:color="{DESTAQUE}" '
               'fo:text-transform="uppercase"', proximo="Termo_Subtitulo")
        + _par("Termo_Subtitulo", 'fo:text-align="center" fo:margin-top="0.06cm" '
               'fo:margin-bottom="0.35cm"',
               f'fo:font-size="9.5pt" fo:color="{CINZA}" fo:letter-spacing="0.05cm" '
               'fo:text-transform="uppercase"')
        + _par("Termo_Secao",
               f'fo:margin-top="0.3cm" fo:margin-bottom="0.1cm" fo:padding-bottom="0.04cm" '
               f'fo:border-bottom="0.75pt solid {FILETE}" fo:keep-with-next="always"',
               f'fo:font-size="8.5pt" fo:font-weight="bold" fo:color="{DESTAQUE}" '
               'fo:letter-spacing="0.03cm" fo:text-transform="uppercase"')
        + _par("Termo_Rotulo", "",
               f'fo:font-size="7.5pt" fo:font-weight="bold" fo:color="{CINZA}" '
               'fo:text-transform="uppercase"')
        + _par("Termo_Valor", "", 'fo:font-size="9.5pt"')
        + _par("Termo_ColCab", 'fo:text-align="center"',
               f'fo:font-size="8pt" fo:font-weight="bold" fo:color="{TINTA}" '
               'fo:letter-spacing="0.03cm" fo:text-transform="uppercase"')
        + _par("Termo_Declaracao",
               'fo:text-align="justify" fo:margin-bottom="0.08cm" fo:line-height="115%"',
               'fo:font-size="7pt"')
        + '<style:style style:name="Termo_Destaque" style:display-name="Termo Destaque" '
          'style:family="text"><style:text-properties fo:font-weight="bold"/></style:style>'
    )
    automaticos = (
        '<style:page-layout style:name="Pagina">'
        '<style:page-layout-properties fo:page-width="21cm" fo:page-height="29.7cm" '
        'style:print-orientation="portrait" fo:margin-top="1cm" fo:margin-bottom="0.9cm" '
        'fo:margin-left="2cm" fo:margin-right="2cm"/>'
        '<style:header-style><style:header-footer-properties fo:min-height="0cm" '
        'fo:margin-bottom="0.3cm"/></style:header-style>'
        '<style:footer-style><style:header-footer-properties fo:min-height="0cm" '
        'fo:margin-top="0.3cm"/></style:footer-style></style:page-layout>'
        '<style:style style:name="CabTab" style:family="table">'
        f'<style:table-properties style:width="{LARGURA}cm" table:align="margins"/></style:style>'
        '<style:style style:name="CabColLogo" style:family="table-column">'
        '<style:table-column-properties style:column-width="5cm"/></style:style>'
        '<style:style style:name="CabColTexto" style:family="table-column">'
        f'<style:table-column-properties style:column-width="{LARGURA - 5}cm"/></style:style>'
        '<style:style style:name="CabCel" style:family="table-cell">'
        '<style:table-cell-properties fo:padding="0cm" fo:border="none" '
        'style:vertical-align="middle"/></style:style>'
        '<style:style style:name="Logo" style:family="graphic">'
        '<style:graphic-properties style:vertical-pos="middle" style:vertical-rel="text" '
        'fo:border="none" fo:padding="0cm"/></style:style>'
    )
    logo = (f'<draw:frame draw:style-name="Logo" draw:name="Logo" text:anchor-type="as-char" '
            f'svg:width="4.2cm" svg:height="{alto}cm" draw:z-index="0">'
            '<draw:image xlink:href="Pictures/logo_tjce.png" xlink:type="simple" '
            'xlink:show="embed" xlink:actuate="onLoad"/></draw:frame>')
    cabecalho = (
        '<table:table table:name="Cabecalho" table:style-name="CabTab">'
        '<table:table-column table:style-name="CabColLogo"/>'
        '<table:table-column table:style-name="CabColTexto"/><table:table-row>'
        f'<table:table-cell table:style-name="CabCel">{_p("Standard", logo)}</table:table-cell>'
        '<table:table-cell table:style-name="CabCel">'
        + _p("Termo_Cab_Estado", "Estado do Ceará · Poder Judiciário")
        + _p("Termo_Cab_Orgao", "Secretaria de Tecnologia da Informação")
        + _p("Termo_Cab_Depto", "Departamento de Infraestrutura de TI")
        + '</table:table-cell></table:table-row></table:table>'
        + _p("Termo_Filete")
    )
    chamado = f" · Chamado {_txt(t.chamado)}" if t.chamado else ""
    rodape = _p("Termo_Rodape",
                f"{_txt(t.titulo)} — {_txt(t.subtitulo.lower())}{chamado} · Página "
                "<text:page-number text:select-page=\"current\"/> de <text:page-count/>")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<office:document-styles {_NS}>'
        '<office:font-face-decls><style:font-face style:name="Arial" '
        'svg:font-family="Arial" style:font-family-generic="swiss"/></office:font-face-decls>'
        f'<office:styles>{nomeados}</office:styles>'
        f'<office:automatic-styles>{automaticos}</office:automatic-styles>'
        '<office:master-styles><style:master-page style:name="Standard" '
        'style:page-layout-name="Pagina">'
        f'<style:header>{cabecalho}</style:header><style:footer>{rodape}</style:footer>'
        '</style:master-page></office:master-styles></office:document-styles>'
    )


_MIME = {".png": "image/png", ".emf": "image/x-emf", ".jpg": "image/jpeg"}


def escrever_odt(destino: "str | pathlib.Path", content: str, styles: str, titulo: str,
                 imagens: "dict[str, pathlib.Path]") -> pathlib.Path:
    """Empacota um .odt (comum aos termos). `imagens` = nome dentro de
    Pictures/ -> arquivo de origem."""
    destino = pathlib.Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    entradas = "".join(
        f'<manifest:file-entry manifest:full-path="Pictures/{nome}" '
        f'manifest:media-type="{_MIME.get(pathlib.Path(nome).suffix.lower(), "image/png")}"/>'
        for nome in imagens)
    manifest = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" '
        'manifest:version="1.3">'
        '<manifest:file-entry manifest:full-path="/" manifest:version="1.3" '
        'manifest:media-type="application/vnd.oasis.opendocument.text"/>'
        '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>'
        '<manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>'
        '<manifest:file-entry manifest:full-path="meta.xml" manifest:media-type="text/xml"/>'
        + entradas + '</manifest:manifest>')
    meta = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<office:document-meta {_NS}><office:meta>'
        '<meta:generator>Automatic</meta:generator>'
        f'<dc:title xmlns:dc="http://purl.org/dc/elements/1.1/">{_txt(titulo)}</dc:title>'
        '</office:meta></office:document-meta>')
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        # O mimetype tem de ser o 1º arquivo e SEM compressão (regra do ODF).
        z.writestr(zipfile.ZipInfo("mimetype"), "application/vnd.oasis.opendocument.text",
                   compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/manifest.xml", manifest)
        z.writestr("content.xml", content)
        z.writestr("styles.xml", styles)
        z.writestr("meta.xml", meta)
        for nome, origem in imagens.items():
            z.write(origem, f"Pictures/{nome}")
    return destino


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #

def gerar_odt(termo: Termo, destino: "str | pathlib.Path") -> pathlib.Path:
    """Grava o termo em `destino` (.odt) e devolve o caminho."""
    return escrever_odt(destino, _content(termo), _styles(termo),
                        f"{termo.titulo} — {termo.subtitulo}", {"logo_tjce.png": LOGO})


def _soffice() -> str:
    for c in (shutil.which("soffice"),
              r"C:\Program Files\LibreOffice\program\soffice.exe",
              r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"):
        if c and pathlib.Path(c).exists():
            return c
    raise FileNotFoundError("LibreOffice não encontrado (soffice.exe).")


def para_pdf(odt: "str | pathlib.Path") -> pathlib.Path:
    """Converte o .odt em PDF (mesma pasta) com o LibreOffice sem janela —
    o PDF é o que vai anexado ao chamado.

    PERFIL PRÓPRIO do LibreOffice: com o perfil normal, se o técnico estiver
    com o Writer aberto, o `--headless` entrega o pedido à janela aberta e
    sai sem converter nada (falha calada)."""
    from services.paths import APP_LOCAL_DIR
    odt = pathlib.Path(odt)
    perfil = (APP_LOCAL_DIR / "libreoffice_perfil").as_uri()
    r = subprocess.run([_soffice(), f"-env:UserInstallation={perfil}", "--headless",
                        "--convert-to", "pdf", "--outdir", str(odt.parent), str(odt)],
                       capture_output=True, timeout=120,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    pdf = odt.with_suffix(".pdf")
    if not pdf.exists():
        erro = (r.stderr or r.stdout or b"").decode(errors="replace").strip()
        raise RuntimeError(f"o LibreOffice não gerou o PDF{': ' + erro[-300:] if erro else ''}")
    return pdf
