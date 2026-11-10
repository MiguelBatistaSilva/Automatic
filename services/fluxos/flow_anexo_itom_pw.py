"""
services/fluxos/flow_anexo_itom_pw.py — Anexa a tela do Itom da máquina ao
chamado (Sala de Imagem), 10/11.

O que o técnico fazia na mão, por chamado:
  1. abre a máquina (o tombo) no Itom, Ctrl+P, salva em PDF em paisagem;
  2. no chamado, clica em Anexos (o clipe da barra), "Escolher arquivo",
     escolhe o PDF, Salvar e Encerrar.

Aqui:
  1. ITOM (Chrome sem janela, o PDF do Chrome só sai assim): para cada tombo,
     a tela Summary da máquina INTEIRA (cabeçalho, abas, todos os dados)
     vira `<HOSTNAME>.pdf` (nome da máquina no Itom, decisão dele) em A4
     paisagem, cortada onde acabam os dados: o Ctrl+P levava junto a barra e a
     área cinza vazias de baixo (pedido dele, 10/11). A tabela da esquerda tem
     rolagem interna que escondia o 'System Serial No': ela é esticada antes.
     O recorte é um print da tela posto num PDF (o PDF do Chrome só sai sem
     janela). PDFs em %LOCALAPPDATA%\\Automatic\\anexos_itom
     (fora do projeto: não dispara o hot-reload).
  2. ASSYST: abre o chamado, `#btAttachment`, põe o PDF em `#fileUploader`,
     Salvar, espera o arquivo aparecer na lista do pop-up e Encerrar.

Pop-up capturado em 10/11 no S2510350 (só leitura, nada salvo): diálogo
`components_AttachmentDialog_N`; campos Arquivo (`#fileUploader`, input file
comum de um form multipart: o arquivo só sobe no Salvar), Nome
(`attachmentForm.name`), Nome de arquivo (`attachmentForm.filename`), Notas;
botões Novo, Salvar, Excluir e Encerrar (`#dialogCancel`); embaixo a lista
"Anexos" com os já anexados.

Sem checkpoint: antes de anexar, o fluxo olha a lista do pop-up; se o PDF
daquela máquina já está lá, pula. Rodar de novo é seguro.

`modo_teste`: escolhe o arquivo e PARA antes do Salvar (Encerrar sem salvar).
"""

import dataclasses
import re
from pathlib import Path

from services.paths import APP_LOCAL_DIR

PASTA_PDF = APP_LOCAL_DIR / "anexos_itom"
_DIALOGO = ".dijitDialog[widgetid^='components_AttachmentDialog']"
# Onde a tela tem dados: do topo até o fim do bloco de conteúdo (abaixo dele
# só há uma barra e a área cinza vazias).
_JS_FIM_DO_CONTEUDO = r"""() => {
    const e = document.querySelector('#mainContentArea1') || document.querySelector('.contentBlock');
    return e ? Math.ceil(e.getBoundingClientRect().bottom) : document.body.scrollHeight; }"""
# Estica as grades com rolagem interna (a da esquerda escondia a última linha).
_JS_EXPANDIR = r"""() => { for (const v of document.querySelectorAll('.x-grid-view')) {
    const d = v.scrollHeight - v.clientHeight; if (d <= 0) continue;
    let e = v;
    for (let i = 0; i < 4 && e; i++, e = e.parentElement)
        if (e.style && e.offsetHeight) e.style.height = (e.offsetHeight + d) + 'px';
    v.style.overflow = 'visible'; } }"""


def _pdf_da_tela(page, destino: Path) -> None:
    """Print da tela inteira, cortado onde acabam os dados -> PDF A4 paisagem.
    A página do Itom é trocada pela imagem: depois, navegue de novo."""
    import base64
    page.evaluate(_JS_EXPANDIR)
    page.wait_for_timeout(300)
    largura = page.evaluate("() => document.documentElement.clientWidth")
    altura = page.evaluate(_JS_FIM_DO_CONTEUDO) + 5
    png = page.screenshot(full_page=True,
                          clip={"x": 0, "y": 0, "width": largura, "height": altura})
    img = base64.b64encode(png).decode()
    page.set_content("<html><body style='margin:0'><img style='width:100%' "
                     f"src='data:image/png;base64,{img}'></body></html>")
    page.pdf(path=str(destino), format="A4", landscape=True, print_background=True,
             margin={"top": "10mm", "bottom": "10mm", "left": "10mm", "right": "10mm"})


@dataclasses.dataclass
class Linha:
    chamado: str
    tombo: str
    host: str = ""
    pdf: str = ""
    situacao: str = ""      # anexado | já anexado | simulado | erro
    detalhe: str = ""


def ler_pares(texto: str) -> tuple[list[Linha], list[str]]:
    """'Chamado,tombo' por linha (aceita ; tab ou espaço). Tombo = os 6
    últimos dígitos. Devolve (linhas, erros)."""
    linhas, erros = [], []
    for n, bruta in enumerate((texto or "").splitlines(), 1):
        if not bruta.strip():
            continue
        partes = [p for p in re.split(r"[,;\t ]+", bruta.strip()) if p]
        if len(partes) != 2:
            erros.append(f"Linha {n}: use 'Chamado,tombo' ({bruta.strip()!r}).")
            continue
        chamado, tombo = partes[0].upper(), re.sub(r"\D", "", partes[1])[-6:]
        if chamado == "CHAMADO":
            continue  # cabeçalho
        if not re.fullmatch(r"[A-Z]?\d{5,}", chamado):
            erros.append(f"Linha {n}: chamado inválido ({partes[0]!r}).")
        elif len(tombo) != 6:
            erros.append(f"Linha {n}: tombo inválido ({partes[1]!r}).")
        else:
            linhas.append(Linha(chamado, tombo))
    return linhas, erros


# --------------------------------------------------------------------------- #
# 1. Itom -> PDF
# --------------------------------------------------------------------------- #

def gerar_pdfs(linhas: list[Linha], matricula: str, senha: str, log) -> None:
    """Preenche host e pdf de cada linha (ou situacao='erro')."""
    from services.assyst.browser_pw import NavegadorPW
    from services.fluxos import flow_itom_pw as itom

    PASTA_PDF.mkdir(parents=True, exist_ok=True)
    feitos: dict[str, tuple[str, str]] = {}      # tombo -> (host, pdf)
    with NavegadorPW(log) as page:               # sem janela (o PDF exige)
        if not itom._login(page, matricula, senha, log):
            for l in linhas:
                l.situacao, l.detalhe = "erro", "o Itom recusou o login"
            return
        for l in linhas:
            if l.tombo in feitos:
                l.host, l.pdf = feitos[l.tombo]
                continue
            log(f"Itom: tombo {l.tombo}...", "status")
            try:
                hosts = itom._hosts(page, l.tombo)
                if not hosts:
                    l.situacao, l.detalhe = "erro", "tombo não encontrado no Itom"
                    log(f"Tombo {l.tombo} não está no Itom.", "error")
                    continue
                h = hosts[0]
                page.goto(f"{itom.BASE}/ITOM/{h['url']}", timeout=30000)
                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(1500)      # as grades terminam de montar
                pdf = PASTA_PDF / f"{h['host']}.pdf"
                _pdf_da_tela(page, pdf)
                l.host, l.pdf = h["host"], str(pdf)
                feitos[l.tombo] = (l.host, l.pdf)
                log(f"PDF gerado: {pdf.name}", "success")
                # A página virou a imagem: volta à busca do Discovery.
                page.goto(f"{itom.BASE}/ITOM/over_view.jsp", timeout=30000)
                page.wait_for_load_state("networkidle", timeout=30000)
            except Exception as e:
                l.situacao, l.detalhe = "erro", f"falha no Itom: {e}"
                log(f"Tombo {l.tombo}: falha no Itom ({e}).", "error")


# --------------------------------------------------------------------------- #
# 2. Assyst -> anexo
# --------------------------------------------------------------------------- #

def _abrir_anexos(page, log):
    # O pop-up do chamado anterior pode ainda estar visível (fechando): ler a
    # lista dele dava falso "já anexado" (10/11, 5 de 13 chamados). Espera
    # sumir antes de abrir o deste chamado.
    for _ in range(40):
        if page.locator(_DIALOGO).filter(visible=True).count() == 0:
            break
        page.wait_for_timeout(250)
    page.wait_for_timeout(500)
    page.locator("#btAttachment").click()
    dlg = page.locator(_DIALOGO).filter(visible=True).last
    dlg.wait_for(state="visible", timeout=15000)
    page.wait_for_timeout(1000)                  # a lista de anexos carrega
    return dlg


def _encerrar(dlg) -> None:
    try:
        dlg.locator("#dialogCancel").click()
    except Exception:
        dlg.page.keyboard.press("Escape")


def anexar(page, log, l: Linha, modo_teste: bool) -> None:
    from services.assyst.browser_pw import _navegar_para_chamado_pw

    nome = Path(l.pdf).name
    if not _navegar_para_chamado_pw(page, l.chamado, log):
        l.situacao, l.detalhe = "erro", "chamado não abriu"
        return
    dlg = _abrir_anexos(page, log)
    if nome.lower() in dlg.inner_text().lower():
        l.situacao, l.detalhe = "já anexado", nome
        log(f"{l.chamado}: {nome} já estava anexado; pulei.", "info")
        _encerrar(dlg)
        return

    dlg.locator("#fileUploader").set_input_files(l.pdf)
    page.wait_for_timeout(500)
    # Nome e Nome de arquivo ficam como o Assyst deixar (o técnico não os
    # preenche; na simulação de 10/11 vieram vazios depois de escolher o PDF).
    campo_nome = dlg.locator("[name='attachmentForm.name']")
    arquivo = dlg.locator("[name='attachmentForm.filename']").input_value()
    preenchido = f"Nome '{campo_nome.input_value()}', arquivo '{arquivo}'"

    if modo_teste:
        l.situacao, l.detalhe = "simulado", preenchido
        log(f"SIMULAÇÃO {l.chamado}: {nome} escolhido ({preenchido}); "
            "parei antes do Salvar.", "success")
        _encerrar(dlg)
        return

    dlg.get_by_role("button", name="Salvar", exact=True).click()
    # Confirmação real: o arquivo aparece na lista "Anexos" do pop-up.
    for _ in range(60):
        page.wait_for_timeout(500)
        if nome.lower() in dlg.inner_text().lower():
            l.situacao, l.detalhe = "anexado", nome
            log(f"{l.chamado}: {nome} anexado.", "success")
            _encerrar(dlg)
            return
    l.situacao, l.detalhe = "erro", "o anexo não apareceu na lista depois do Salvar"
    log(f"{l.chamado}: {nome} não apareceu na lista de anexos em 30 s. "
        "Confira o chamado.", "error")
    _encerrar(dlg)


def ler_chamados(texto: str) -> tuple[list[str], list[str]]:
    """Um chamado por linha (aceita também vírgula, ; ou espaço). Sem repetir.
    Devolve (chamados, erros)."""
    chamados, erros = [], []
    for bruto in re.split(r"[\s,;]+", texto or ""):
        if not bruto:
            continue
        c = bruto.upper()
        if not re.fullmatch(r"[A-Z]?\d{5,}", c):
            erros.append(f"Chamado inválido: {bruto!r}.")
        elif c not in chamados:
            chamados.append(c)
    return chamados, erros


def anexar_documento(chamados: list[str], pdf: str, matricula: str, senha: str,
                     log, modo_teste: bool = False) -> list[Linha]:
    """'Importar documento' (10/11): o mesmo PDF anexado a vários chamados.
    Pula o chamado que já tem um anexo com o mesmo nome de arquivo."""
    from services.assyst.browser_pw import NavegadorPW, _fazer_login_pw

    linhas = [Linha(c, "", pdf=pdf) for c in chamados]
    log(f"Anexando {Path(pdf).name} a {len(linhas)} chamado(s)...", "status")
    with NavegadorPW(log) as page:
        if not _fazer_login_pw(page, matricula, senha, log):
            for l in linhas:
                l.situacao, l.detalhe = "erro", "falha no login do Assyst"
        else:
            for l in linhas:
                try:
                    anexar(page, log, l, modo_teste)
                except Exception as e:
                    l.situacao, l.detalhe = "erro", str(e)
                    log(f"{l.chamado}: erro ao anexar ({e}).", "error")

    ok = sum(l.situacao in ("anexado", "já anexado", "simulado") for l in linhas)
    log(f"Fim: {ok} de {len(linhas)} ok.", "success" if ok == len(linhas) else "error")
    for l in linhas:
        log(f"  {l.chamado} → {l.situacao}"
            + (f" ({l.detalhe})" if l.situacao == "erro" else ""), "info")
    return linhas


def executar(linhas: list[Linha], matricula: str, senha: str, log,
             modo_teste: bool = False) -> list[Linha]:
    from services.assyst.browser_pw import NavegadorPW, _fazer_login_pw

    log(f"{len(linhas)} chamado(s). 1/2: gerando os PDFs no Itom...", "status")
    gerar_pdfs(linhas, matricula, senha, log)
    pendentes = [l for l in linhas if l.pdf and not l.situacao]
    if pendentes:
        log("2/2: anexando no Assyst...", "status")
        with NavegadorPW(log) as page:
            if not _fazer_login_pw(page, matricula, senha, log):
                for l in pendentes:
                    l.situacao, l.detalhe = "erro", "falha no login do Assyst"
            else:
                for l in pendentes:
                    try:
                        anexar(page, log, l, modo_teste)
                    except Exception as e:
                        l.situacao, l.detalhe = "erro", str(e)
                        log(f"{l.chamado}: erro ao anexar ({e}).", "error")

    ok = sum(l.situacao in ("anexado", "já anexado", "simulado") for l in linhas)
    log(f"Fim: {ok} de {len(linhas)} ok.", "success" if ok == len(linhas) else "error")
    for l in linhas:
        log(f"  {l.chamado} · {l.tombo} · {l.host or '—'} → {l.situacao}"
            + (f" ({l.detalhe})" if l.situacao == "erro" else ""), "info")
    return linhas
