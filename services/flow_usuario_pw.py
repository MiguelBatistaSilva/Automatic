"""
services/flow_usuario_pw.py — Fluxo "Aguardando Info do Usuário *" em Playwright.

Só existe no bot (Telegram) — não tem tela no app desktop. Mesma família do
`flow_fornecedor_pw.py`/`flow_informacao_pw.py` (e do `flow_atendimento_pw.py`):
mesmo menu, mesmo tipo de pop-up de ação, só muda o item clicado.

Caminho no Assyst:
    Ações -> Ações de relógio -> Aguardando Info do Usuário * -> texto -> Salvar ação.

SELETOR SÓ POR TEXTO, DE PROPÓSITO: mesmo caso de 'Adicionar Informação' e
'Aguardando Info do Fornecedor' — sem id numérico capturado no registry
Dojo (só 'Atendimento Iniciado' tem, id 227). O `*` no final É PARTE DO
RÓTULO no Assyst — confirmado com o Miguel, não é ênfase.

Ver memoria: project_flow_fornecedor_bot, project_flow_informacao_bot.
"""

from services.browser_pw import _navegar_para_chamado_pw

_SEL_MENU_ACOES = "#menuActions"
_SEL_ACOES_RELOGIO = "td.dijitMenuItemLabel:text-is('Ações de relógio')"
_SEL_AGUARDANDO_USUARIO_TXT = "td.dijitMenuItemLabel:text-is('Aguardando Info do Usuário *')"
_SEL_DIALOGO = "#ManageActionForm_actionDialog"
_SEL_SALVAR = "[id='ManageActionForm.btSave']"
_SEL_IFRAME_EDITOR = "iframe[title*='formattedRemarks']"


def _preencher_texto_dialog(page, log, texto: str) -> bool:
    """
    Preenche o texto no editor do POP-UP da ação.

    Mesma logica e mesmo motivo de `_preencher_texto_dialog` em
    flow_fornecedor_pw.py/flow_informacao_pw.py (mira o ULTIMO editor
    'formattedRemarks' da tela — o do pop-up, não o do evento — e digita em
    vez de innerHTML para atualizar o modelo interno do CKEditor).
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


def aguardar_info_usuario(page, log, numero_chamado: str, informacao: str,
                          modo_teste: bool = False) -> bool:
    """
    Adiciona uma informação (texto livre) a um chamado, via 'Ações de
    relógio -> Aguardando Info do Usuário *'.

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

    # 4. Clicar em 'Aguardando Info do Usuário *'
    try:
        page.click(_SEL_AGUARDANDO_USUARIO_TXT, timeout=10000)
        log("Clicado em 'Aguardando Info do Usuário *'.", "success")
    except Exception as e:
        log(f"Erro ao clicar em 'Aguardando Info do Usuário *': {e}", "error")
        log("Confirme que essa acao esta disponivel no chamado e que o "
            "texto do botao no Assyst e exatamente "
            "'Aguardando Info do Usuário *' (com o asterisco).", "info")
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

    log(f"Aguardando Info do Usuário registrado com sucesso no chamado "
        f"{numero_chamado}.", "success")
    return True
