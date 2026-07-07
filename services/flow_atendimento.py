"""
services/flow_atendimento.py — Fluxo "Iniciar Atendimento".

Inicia um chamado que esta em Atendimento Programado (relogio de SLA pausado).
Caminho no Assyst:
    Ações -> Ações de relógio -> Atendimento Iniciado -> descricao -> Salvar ação.

Seletores confirmados por captura do registry Dojo (2026-07-06):
  - Botao 'Ações'                 -> id 'menuActions'
  - Submenu 'Ações de relógio'    -> PopupMenuItem (rotulo em PT), por texto
  - Item 'Atendimento Iniciado'   -> id 'menuActions_$TakeAction(227)_ClockActions'
    (227 = tipo de acao global no Assyst; estavel por chamado/sessao)

Ver memoria: project_flow_atendimento, project_ckeditor_fix, project_sla_regras.
"""
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time

from services.flow_utils import _navegar_para_chamado

DESCRICAO_PADRAO = "Contato com êxito, suporte realizando intervenção técnica."

# Item "Atendimento Iniciado" — id estavel (tipo de acao 227).
_XPATH_ATEND_INICIADO_ID = "//*[@id='menuActions_$TakeAction(227)_ClockActions']"
_XPATH_ATEND_INICIADO_TXT = (
    "//td[contains(@class,'dijitMenuItemLabel') and "
    "normalize-space(.)='Atendimento Iniciado']"
)
_XPATH_ACOES_RELOGIO = (
    "//td[contains(@class,'dijitMenuItemLabel') and "
    "normalize-space(.)='Ações de relógio']"
)


def _preencher_descricao_dialog(driver, log, descricao: str) -> bool:
    """
    Preenche a descricao no editor do POP-UP da acao. Diferente de
    _preencher_descricao (que pega o 1o iframe), aqui miramos o ULTIMO iframe
    'formattedRemarks' — o do pop-up e o mais recente no DOM, enquanto o 1o e o
    do proprio evento. Escrever no 1o gravaria no lugar errado.
    """
    try:
        iframes = WebDriverWait(driver, 15).until(
            lambda d: d.find_elements(
                By.XPATH, "//iframe[contains(@title,'formattedRemarks')]"
            ) or False
        )
        titulos = [f.get_attribute("title") for f in iframes]
        log(f"[DIAG] iframes 'formattedRemarks' na tela: {titulos}", "info")

        iframe = iframes[-1]  # o do pop-up
        driver.switch_to.frame(iframe)
        corpo = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body.cke_editable"))
        )
        driver.execute_script(
            "arguments[0].innerHTML = arguments[1];",
            corpo, descricao.replace("\n", "<br>"),
        )
        driver.switch_to.default_content()
        log("Descricao da acao preenchida (ultimo editor).", "success")
        return True
    except Exception as e:
        log(f"Erro ao preencher a descricao da acao: {e}", "error")
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
        return False


def iniciar_atendimento(driver, log, numero_chamado: str,
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
    if not _navegar_para_chamado(driver, numero_chamado, log):
        log(f"Nao foi possivel abrir o chamado {numero_chamado}.", "error")
        return False

    # 2. Abrir o menu 'Ações'
    try:
        WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.ID, "menuActions"))
        ).click()
        log("Menu 'Ações' aberto.", "success")
        time.sleep(1)
    except Exception as e:
        log(f"Erro ao abrir o menu 'Ações': {e}", "error")
        return False

    # 3. Revelar o submenu 'Ações de relógio' (passa o mouse por cima)
    try:
        sub = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, _XPATH_ACOES_RELOGIO))
        )
        ActionChains(driver).move_to_element(sub).perform()
        log("Submenu 'Ações de relógio' revelado.", "success")
        time.sleep(1)
    except Exception as e:
        log(f"Erro ao revelar 'Ações de relógio': {e}", "error")
        return False

    # 4. Clicar em 'Atendimento Iniciado' (id estavel 227; fallback por texto)
    try:
        alvo = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, _XPATH_ATEND_INICIADO_ID))
        )
        try:
            alvo.click()
        except Exception:
            driver.execute_script("arguments[0].click();", alvo)
        log("Clicado em 'Atendimento Iniciado'.", "success")
        time.sleep(2)
    except Exception:
        try:
            alvo = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, _XPATH_ATEND_INICIADO_TXT))
            )
            driver.execute_script("arguments[0].click();", alvo)
            log("Clicado em 'Atendimento Iniciado' (por texto).", "success")
            time.sleep(2)
        except Exception as e:
            log(f"Erro ao clicar em 'Atendimento Iniciado': {e}", "error")
            log("Confirme que essa acao esta disponivel no chamado "
                "(so aparece com o relogio pausado / no estado certo).", "info")
            return False

    # 5. Preencher a descricao no pop-up (mira o editor do pop-up)
    if not _preencher_descricao_dialog(driver, log, descricao):
        log("Nao foi possivel preencher a descricao da acao.", "error")
        return False

    # 6. Modo teste: para aqui, sem salvar
    if modo_teste:
        log("MODO TESTE: descricao preenchida. Parando ANTES de 'Salvar ação'. "
            "Nada foi alterado no chamado.", "status")
        return True

    # 7. Salvar acao — 'Salvar ação' = id 'ManageActionForm.btSave' (confirmado por
    # captura do pop-up; mesmo id do form de acao da KB). Clique nativo, JS de fallback.
    try:
        btn = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.ID, "ManageActionForm.btSave"))
        )
        try:
            btn.click()
        except Exception:
            driver.execute_script("arguments[0].click();", btn)
        log("Acao salva ('Salvar ação').", "success")
        time.sleep(2)
    except Exception as e:
        log(f"Erro ao clicar em 'Salvar ação': {e}", "error")
        return False

    log(f"Atendimento iniciado com sucesso no chamado {numero_chamado}.", "success")
    return True
