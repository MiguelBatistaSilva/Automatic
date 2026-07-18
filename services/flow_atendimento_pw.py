"""
services/flow_atendimento_pw.py — Fluxo "Iniciar Atendimento" em Playwright.

Gemeo do `services/flow_atendimento.py` (Selenium), que segue intacto para
consulta e rollback. Mesma interface publica, trocando `driver` por `page`.

Inicia um chamado que esta em Atendimento Programado (relogio de SLA pausado).
Caminho no Assyst:
    Ações -> Ações de relógio -> Atendimento Iniciado -> descricao -> Salvar ação.

Seletores confirmados por captura do registry Dojo (2026-07-06):
  - Botao 'Ações'                 -> id 'menuActions'
  - Submenu 'Ações de relógio'    -> PopupMenuItem (rotulo em PT), por texto
  - Item 'Atendimento Iniciado'   -> id 'menuActions_$TakeAction(227)_ClockActions'
    (227 = tipo de acao global no Assyst; estavel por chamado/sessao)
  - Dialogo da acao               -> id 'ManageActionForm_actionDialog'
  - Botao 'Salvar ação'           -> id 'ManageActionForm.btSave'

Ver memoria: project_flow_atendimento, project_ckeditor_fix, project_sla_regras.
"""

from playwright.sync_api import TimeoutError as PWTimeout

from services.browser_pw import _navegar_para_chamado_pw

DESCRICAO_PADRAO = "Contato com êxito, suporte realizando intervenção técnica."

_SEL_MENU_ACOES = "#menuActions"
# Ids com '$', '(' e '.' quebram o parser de CSS; o seletor por ATRIBUTO evita
# ter que escapar cada caractere especial.
_SEL_ATEND_INICIADO_ID = "[id='menuActions_$TakeAction(227)_ClockActions']"
_SEL_ATEND_INICIADO_TXT = "td.dijitMenuItemLabel:text-is('Atendimento Iniciado')"
_SEL_ACOES_RELOGIO = "td.dijitMenuItemLabel:text-is('Ações de relógio')"
_SEL_DIALOGO = "#ManageActionForm_actionDialog"
_SEL_SALVAR = "[id='ManageActionForm.btSave']"
_SEL_IFRAME_EDITOR = "iframe[title*='formattedRemarks']"


def _preencher_descricao_dialog(page, log, descricao: str) -> bool:
    """
    Preenche a descricao no editor do POP-UP da acao.

    Ha dois editores 'formattedRemarks' na tela: o do proprio evento e o do
    pop-up. O do pop-up e o MAIS RECENTE no DOM, por isso miramos o ULTIMO —
    escrever no primeiro gravaria no lugar errado.

    Diferente do fluxo Selenium (que usava innerHTML), aqui a descricao e
    DIGITADA. O innerHTML nao atualiza o modelo interno do CKEditor, que foi a
    causa raiz do bug da descricao repetida; digitar atualiza. Mesmo tratamento
    ja aplicado ao _preencher_descricao do fluxo principal.
    """
    try:
        total = page.locator(_SEL_IFRAME_EDITOR).count()
        log(f"[DIAG] editores 'formattedRemarks' na tela: {total}", "info")

        # frame_locator resolve o iframe a cada uso e ja espera por ele, entao
        # nao existe o switch_to.frame/default_content nem o risco de ficar
        # preso num frame se algo estourar no meio.
        editor = page.frame_locator(_SEL_IFRAME_EDITOR).last
        corpo = editor.locator("body.cke_editable")
        corpo.wait_for(state="visible", timeout=15000)

        corpo.click()
        corpo.press("Control+a")
        corpo.press("Delete")

        linhas = descricao.split("\n")
        for i, linha in enumerate(linhas):
            if i > 0:
                corpo.press("Enter")
            if linha:
                corpo.press_sequentially(linha)

        log("Descricao da acao preenchida (ultimo editor).", "success")
        return True
    except Exception as e:
        log(f"Erro ao preencher a descricao da acao: {e}", "error")
        return False


def iniciar_atendimento(page, log, numero_chamado: str,
                        descricao: str = DESCRICAO_PADRAO,
                        modo_teste: bool = False) -> bool:
    """
    Inicia o atendimento de um chamado em Atendimento Programado.

    modo_teste=True  -> vai ate preencher a descricao e PARA (nao clica em
                        'Salvar ação', nao altera o chamado).
    modo_teste=False -> completa a acao clicando em 'Salvar ação'.

    Retorna True se chegou ao fim esperado, False em qualquer falha.
    """
    numero_chamado = numero_chamado.strip()

    # 1. Navegar ate o chamado
    if not _navegar_para_chamado_pw(page, numero_chamado, log):
        log(f"Nao foi possivel abrir o chamado {numero_chamado}.", "error")
        return False

    # 2. Abrir o menu 'Ações'
    try:
        page.click(_SEL_MENU_ACOES, timeout=20000)
        log("Menu 'Ações' aberto.", "success")
    except PWTimeout as e:
        log(f"Erro ao abrir o menu 'Ações': {e}", "error")
        return False

    # 3. Revelar o submenu 'Ações de relógio' (passa o mouse por cima)
    try:
        page.hover(_SEL_ACOES_RELOGIO, timeout=10000)
        log("Submenu 'Ações de relógio' revelado.", "success")
    except PWTimeout as e:
        log(f"Erro ao revelar 'Ações de relógio': {e}", "error")
        return False

    # 4. Clicar em 'Atendimento Iniciado' (id estavel 227; fallback por texto)
    try:
        page.click(_SEL_ATEND_INICIADO_ID, timeout=10000)
        log("Clicado em 'Atendimento Iniciado'.", "success")
    except PWTimeout:
        try:
            page.click(_SEL_ATEND_INICIADO_TXT, timeout=5000)
            log("Clicado em 'Atendimento Iniciado' (por texto).", "success")
        except PWTimeout as e:
            log(f"Erro ao clicar em 'Atendimento Iniciado': {e}", "error")
            log("Confirme que essa acao esta disponivel no chamado "
                "(so aparece com o relogio pausado / no estado certo).", "info")
            return False

    # 5. Esperar o pop-up da acao. No fluxo Selenium havia um sleep(2) fixo aqui;
    # agora espera-se o dialogo existir de fato antes de mexer no editor.
    try:
        page.locator(_SEL_DIALOGO).wait_for(state="visible", timeout=15000)
        log("Pop-up da acao aberto.", "success")
    except PWTimeout as e:
        log(f"O pop-up da acao nao abriu: {e}", "error")
        return False

    # 6. Preencher a descricao no pop-up (mira o editor do pop-up)
    if not _preencher_descricao_dialog(page, log, descricao):
        log("Nao foi possivel preencher a descricao da acao.", "error")
        return False

    # 7. Modo teste: para aqui, sem salvar
    if modo_teste:
        log("MODO TESTE: descricao preenchida. Parando ANTES de 'Salvar ação'. "
            "Nada foi alterado no chamado.", "status")
        return True

    # 8. Salvar acao
    try:
        page.click(_SEL_SALVAR, timeout=15000)
        log("Acao salva ('Salvar ação').", "success")
    except PWTimeout as e:
        log(f"Erro ao clicar em 'Salvar ação': {e}", "error")
        return False

    # 9. Confirmar que o pop-up fechou — sinal de que o Assyst aceitou a acao.
    # Sem isso, um erro de validacao no dialogo passaria por "sucesso".
    try:
        page.locator(_SEL_DIALOGO).wait_for(state="hidden", timeout=15000)
    except PWTimeout:
        log("O pop-up nao fechou apos salvar — a acao pode NAO ter sido "
            "registrada. Confira o chamado manualmente.", "error")
        return False

    log(f"Atendimento iniciado com sucesso no chamado {numero_chamado}.", "success")
    return True
