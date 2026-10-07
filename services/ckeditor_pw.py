"""
services/ckeditor_pw.py — Texto FORMATADO (com cor) no CKEditor do Assyst.

Os fluxos digitam a descrição (press_sequentially), o que não permite cor. O
padrão de texto da auditoria (2026-09-30) exige cor — azul marinho no texto,
vermelho nos dados — então aqui o conteúdo entra pela API do próprio CKEditor
(`setData` + `updateElement`), que atualiza o MODELO do editor. Não confundir
com o innerHTML antigo, que só mexia no DOM e causou o bug da descrição
repetida em cadeia.

Validado em 2026-09-30 no pop-up de Atendimento Programado (CKEditor 4.3.2,
instância `rtNONE_formattedRemarks`), pelo teste_programar_atendimento.py.
O nome da instância NÃO é fixado: é descoberto pelo iframe na hora.
"""

import html
import re

AZUL_MARINHO = "#000080"
VERMELHO = "#FF0000"

_SEL_IFRAME_EDITOR = "iframe[title*='formattedRemarks']"
_SEL_DIALOGO = "#ManageActionForm_actionDialog"

# Instância do editor do POP-UP: a instância do CKEditor cujo quadro
# (`ed.container`) está VISÍVEL dentro do pop-up de ação VISÍVEL.
#
# Histórico: (1) comparava o iframe com `ed.window` — só existe depois que o
# editor fica pronto; (2) usava o id do <textarea> do pop-up como nome da
# instância — no Resolvido do R2470669 (02/10) isso pegou um editor que NÃO
# era o da tela: o texto "entrou", a leitura de volta confirmou, mas o campo
# visível ficou vazio e o Assyst recusou com "Descrição necessária". O Assyst
# reaproveita o mesmo nome (rtNONE_formattedRemarks) entre pop-ups, então o
# nome não identifica o editor visível; a posição na tela, sim.
_JS_INSTANCIA_POPUP = """(sel) => {
    if (!window.CKEDITOR) return {erro: 'CKEDITOR não carregado'};
    const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
    const dlg = Array.from(document.querySelectorAll(sel)).filter(vis).pop();
    if (!dlg) return {erro: 'nenhum pop-up de ação visível'};
    const cands = Object.entries(CKEDITOR.instances).map(([nome, ed]) => {
        const c = ed.container && ed.container.$;
        return {nome, status: ed.status, dentro: !!(c && dlg.contains(c)),
                visivel: !!(c && vis(c))};
    });
    const bons = cands.filter(c => c.dentro && c.visivel);
    if (!bons.length) return {erro: 'nenhum editor visível dentro do pop-up', cands};
    const b = bons[bons.length - 1];
    return {nome: b.nome, status: b.status, cands};
}"""

# O que está ESCRITO no editor que aparece na tela (o corpo do iframe dele) —
# a prova de que o texto foi para o lugar certo, não só para o modelo interno.
_JS_TEXTO_VISIVEL = """(nome) => {
    const ed = CKEDITOR.instances[nome];
    const f = ed && ed.container && ed.container.$.querySelector('iframe');
    try { return (f && f.contentDocument && f.contentDocument.body.innerText) || ''; }
    catch (e) { return ''; }
}"""

# Espera o editor ficar 'ready' — setData antes disso pode nunca terminar.
_JS_ESPERAR_PRONTO = """(nome) => new Promise(ok => {
    const ed = CKEDITOR.instances[nome];
    if (ed.status === 'ready') return ok('ready');
    ed.once('instanceReady', () => ok('ready'));
    setTimeout(() => ok(ed.status), 10000);
})"""

# Escreve com `insertHtml`, NÃO com `setData` (troca de 02/10).
# O setData RECARREGA o documento do iframe antes de escrever; no Assyst essa
# recarga às vezes não termina: o callback nunca vinha (o teste do Programado
# travou para sempre ali) e, com limite de tempo, o MODELO ficava com o texto
# mas o campo NA TELA ficava vazio — o Assyst recusava com "Descrição
# necessária" (Resolvido do R2470669). O insertHtml escreve direto no corpo já
# carregado (como colar), é síncrono e passa pelo editor (desfazer, filtro).
_JS_SET_DATA = """([nome, conteudo]) => {
    const ed = CKEDITOR.instances[nome];
    ed.focus();
    ed.editable().setHtml('');
    ed.insertHtml(conteudo);
    ed.updateElement();
    ed.fire('change');
    return 'insertHtml';
}"""


def trecho(texto: str, cor: str) -> str:
    """Um pedaço de texto colorido. Tudo que vem de fora passa por escape."""
    return f'<span style="color:{cor}">{html.escape(texto)}</span>'


def paragrafo(*trechos: str) -> str:
    return "<p>" + "".join(trechos) + "</p>"


def texto_livre(texto: str, cor: str = AZUL_MARINHO) -> str:
    """Texto livre (pode ter várias linhas) inteiro numa cor: cada linha vira
    um parágrafo, como o Enter da digitação fazia. Linha em branco vira
    `&nbsp;` — parágrafo vazio o navegador esconde e o espaço sumia."""
    return "".join(
        paragrafo(trecho(linha, cor)) if linha.strip() else "<p>&nbsp;</p>"
        for linha in texto.split("\n")
    )


_RE_PARAGRAFO = re.compile(r"<p>(.*?)</p>", re.S)


def compactar(conteudo_html: str) -> str:
    """Parágrafos -> UM parágrafo com quebras de linha (<br>, o Shift+Enter).

    No CKEditor do Assyst cada <p> tem margem em cima e embaixo: um parágrafo
    por linha, mais os `<p>&nbsp;</p>` das linhas em branco, ficava com cara
    de espaçamento duplo (reclamação do usuário no script do Resolvido, 07/10).
    Linha em branco continua existindo (vira <br><br>), só sem a margem extra.

    Feito AQUI, na entrada do editor, e não em cada montar_texto: vale para
    todos os textos formatados sem mexer nos arquivos de fluxo. Conteúdo que
    não seja só uma sequência de <p> passa intacto.
    """
    if _RE_PARAGRAFO.sub("", conteudo_html).strip():  # tem algo além de <p>s
        return conteudo_html
    linhas = ["" if l.strip() == "&nbsp;" else l
              for l in _RE_PARAGRAFO.findall(conteudo_html)]
    if len(linhas) < 2:
        return conteudo_html
    return "<p>" + "<br>".join(linhas) + "</p>"


def preencher_formatado_popup(page, log, conteudo_html: str) -> bool:
    """Coloca `conteudo_html` no editor do pop-up de ação (o último da tela) e
    confere lendo de volta. True se o editor ficou com o conteúdo."""
    conteudo_html = compactar(conteudo_html)
    try:
        # Espera o editor DO POP-UP existir. Esperar "o último iframe visível"
        # (como antes) passava na hora quando o editor do pop-up ainda não
        # tinha sido criado — o último era o do próprio chamado, sempre
        # visível — e o texto podia ir para o editor errado (bug de 01/10).
        try:
            page.wait_for_function(
                "(sel) => { const r = (" + _JS_INSTANCIA_POPUP + ")(sel); return !r.erro; }",
                arg=_SEL_DIALOGO, timeout=15000)
        except Exception:
            pass  # o diagnóstico abaixo diz o que faltou
        achado = page.evaluate(_JS_INSTANCIA_POPUP, _SEL_DIALOGO)
        if achado.get("erro"):
            log(f"Não achei o editor de texto do pop-up: {achado['erro']} "
                f"(instâncias: {achado.get('cands')}).", "error")
            return False
        nome = achado["nome"]
        log(f"Editor do pop-up: {nome} ({achado['status']}).", "info")
        status = page.evaluate(_JS_ESPERAR_PRONTO, nome)
        if status != "ready":
            log(f"O editor do pop-up não ficou pronto (status: {status}).", "error")
            return False
        como = page.evaluate(_JS_SET_DATA, [nome, conteudo_html])
        # Confere no editor que APARECE na tela, não no modelo interno: o
        # modelo dizia "preenchido" enquanto o campo visível estava vazio
        # (Resolvido do R2470669, 02/10).
        visivel = page.evaluate(_JS_TEXTO_VISIVEL, nome).strip()
        if not visivel:
            log(f"O campo de descrição continua vazio na tela ({como}; "
                f"instâncias: {achado.get('cands')}).", "error")
            return False
        log("Descrição formatada preenchida.", "success")
        return True
    except Exception as e:
        log(f"Erro ao preencher a descrição formatada: {e}", "error")
        return False
