"""
services/flow_informacao_pw.py — Fluxo "Adicionar Informação" em Playwright.

Só existe no bot (Telegram) — não tem tela no app desktop. Mesma família do
`flow_atendimento_pw.py`: mesmo menu, mesmo tipo de pop-up de ação, só muda o
item clicado e o texto digitado nele.

Caminho no Assyst:
    Ações -> Ações de relógio -> Adicionar Informação -> texto -> Salvar ação.

SELETOR SÓ POR TEXTO, DE PROPÓSITO: ao contrário de 'Atendimento Iniciado'
(que tem o id estável `menuActions_$TakeAction(227)_ClockActions`, capturado
no registry Dojo), 'Adicionar Informação' não teve esse id capturado ainda.
Se um dia o texto do botão mudar no Assyst, este seletor quebra silenciosamente
até alguém recapturar o id certo.

Ver memoria: project_flow_atendimento, project_ckeditor_fix.
"""

from services.browser_pw import _navegar_para_chamado_pw

# Excepts largos DE PROPOSITO, mesmo motivo do flow_atendimento_pw: o
# Playwright levanta `playwright.sync_api.Error` (não só PWTimeout) em
# situações comuns aqui — elemento desprendido no meio do clique, target
# fechado. Capturar só PWTimeout deixava isso furar o fluxo e derrubar o
# LOTE inteiro em vez de falhar só um chamado.

_SEL_MENU_ACOES = "#menuActions"
_SEL_ACOES_RELOGIO = "td.dijitMenuItemLabel:text-is('Ações de relógio')"
_SEL_ADD_INFO_TXT = "td.dijitMenuItemLabel:text-is('Adicionar Informação')"
_SEL_DIALOGO = "#ManageActionForm_actionDialog"
_SEL_SALVAR = "[id='ManageActionForm.btSave']"
_SEL_IFRAME_EDITOR = "iframe[title*='formattedRemarks']"


def _preencher_texto_dialog(page, log, texto: str) -> bool:
    """
    Preenche o texto no editor do POP-UP da ação.

    Ha dois editores 'formattedRemarks' na tela: o do proprio evento e o do
    pop-up. O do pop-up e o MAIS RECENTE no DOM, por isso miramos o ULTIMO —
    escrever no primeiro gravaria no lugar errado. Mesma logica e mesmo motivo
    de `_preencher_descricao_dialog` em flow_atendimento_pw.py (digitar, não
    innerHTML, para atualizar o modelo interno do CKEditor).
    """
    try:
        editor = page.frame_locator(_SEL_IFRAME_EDITOR).last
        corpo = editor.locator("body.cke_editable")
        corpo.wait_for(state="visible", timeout=15000)

        corpo.click()
        corpo.press("Control+a")
        corpo.press("Delete")

        linhas = texto.split("\n")
        for i, linha in enumerate(linhas):
            if i > 0:
                corpo.press("Enter")
            if linha:
                corpo.press_sequentially(linha)

        log("Texto da informação preenchido (ultimo editor).", "success")
        return True
    except Exception as e:
        log(f"Erro ao preencher o texto da informacao: {e}", "error")
        return False


def adicionar_informacao(page, log, numero_chamado: str, informacao: str,
                         modo_teste: bool = False) -> bool:
    """
    Adiciona uma informação (texto livre) a um chamado, via 'Ações de
    relógio -> Adicionar Informação'.

    modo_teste=True  -> vai ate preencher o texto e PARA (nao clica em
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
    except Exception as e:
        log(f"Erro ao abrir o menu 'Ações': {e}", "error")
        return False

    # 3. Revelar o submenu 'Ações de relógio' (passa o mouse por cima)
    try:
        page.hover(_SEL_ACOES_RELOGIO, timeout=10000)
        log("Submenu 'Ações de relógio' revelado.", "success")
    except Exception as e:
        log(f"Erro ao revelar 'Ações de relógio': {e}", "error")
        return False

    # 4. Clicar em 'Adicionar Informação'
    try:
        page.click(_SEL_ADD_INFO_TXT, timeout=10000)
        log("Clicado em 'Adicionar Informação'.", "success")
    except Exception as e:
        log(f"Erro ao clicar em 'Adicionar Informação': {e}", "error")
        log("Confirme que essa acao esta disponivel no chamado e que o "
            "texto do botao no Assyst e exatamente 'Adicionar Informação'.",
            "info")
        return False

    # 5. Esperar o pop-up da acao
    try:
        page.locator(_SEL_DIALOGO).wait_for(state="visible", timeout=15000)
        log("Pop-up da ação aberto.", "success")
    except Exception as e:
        log(f"O pop-up da ação não abriu: {e}", "error")
        return False

    # 6. Preencher o texto no pop-up (mira o editor do pop-up)
    if not _preencher_texto_dialog(page, log, informacao):
        log("Nao foi possivel preencher o texto da informacao.", "error")
        return False

    # 7. Modo teste: para aqui, sem salvar
    if modo_teste:
        log("MODO TESTE: texto preenchido. Parando ANTES de 'Salvar ação'. "
            "Nada foi alterado no chamado.", "status")
        return True

    # 8. Salvar acao
    try:
        page.click(_SEL_SALVAR, timeout=15000)
        log("Acao salva ('Salvar ação').", "success")
    except Exception as e:
        log(f"Erro ao clicar em 'Salvar ação': {e}", "error")
        return False

    # 9. Confirmar que o pop-up fechou — sinal de que o Assyst aceitou a acao.
    try:
        page.locator(_SEL_DIALOGO).wait_for(state="hidden", timeout=15000)
    except Exception:
        log("O pop-up não fechou apos salvar — a acao pode NAO ter sido "
            "registrada. Confira o chamado manualmente.", "error")
        return False

    log(f"Informação adicionada com sucesso no chamado {numero_chamado}.", "success")
    return True
