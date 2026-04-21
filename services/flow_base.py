from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time
from services import locators

_URL_HOME = "https://cati.tjce.jus.br/assystweb/application.do"
_URL_CHAMADO = (
    "https://cati.tjce.jus.br/assystweb/application.do"
    "#event%2FDisplayEvent.do%3Fdispatch%3DgetEvent"
    "%26checkJukeBoxSettings%3Dtrue%26eventId%3D{id_final}%26resultSet%3D"
)


def _normalizar_id_assyst(numero: str) -> str:
    """Converte o número visível do chamado para o eventId interno do Assyst."""
    n = str(numero).strip().upper()
    if n.startswith("S2"):
        return n.replace("S2", "7")
    if n.startswith("R"):
        return n.replace("R2", "7")
    if n.isdigit():
        return f"1{n}"
    return n

_ERR_CREDENCIAIS = (By.CSS_SELECTOR, "ol.errormsg")
_ERR_LICENCA = (By.CSS_SELECTOR, "ol.axios-logout-error")
_HOME_LOADED = (By.ID, "resource-container")


def _fazer_login(driver, usuario: str, senha: str, log) -> bool:
    """
    Tenta realizar o login de forma agressiva para licenças,
    mas para imediatamente se a senha estiver errada.
    """
    while True:
        driver.get(_URL_HOME)
        time.sleep(0.5)

        # 1. Verifica se já caiu direto na home (sessão restaurada)
        if not driver.find_elements(By.ID, "login-user") and "application.do" in driver.current_url:
            if not driver.find_elements(By.CSS_SELECTOR, "ol.axios-logout-error"):
                log("✅ Sessão ativa ou login realizado!", "success")
                return True

        try:
            user_field = driver.find_element(By.ID, "login-user")
            user_field.clear()
            user_field.send_keys(usuario)

            pass_field = driver.find_element(By.ID, "login-password")
            pass_field.clear()
            pass_field.send_keys(senha)

            driver.find_element(By.ID, "loginSubmit").click()
        except Exception:
            pass

        # 3. ANÁLISE IMEDIATA DE RETORNO
        time.sleep(1.5)

        # --- CASO A: SENHA ERRADA (PARA TUDO) ---
        erro_credencial = driver.find_elements(By.CSS_SELECTOR, "ol.errormsg")
        if erro_credencial and erro_credencial[0].is_displayed():
            log(f"❌ ERRO CRÍTICO: {erro_credencial[0].text}. Verifique sua senha!", "error")
            return False

        # --- CASO B: LIMITE DE LICENÇA (TENTA NOVAMENTE IMEDIATAMENTE) ---
        erro_licenca = driver.find_elements(By.CSS_SELECTOR, "ol.axios-logout-error")
        if erro_licenca and erro_licenca[0].is_displayed():
            log("⏳ Licença cheia. Re-tentando acesso imediato...", "status")
            continue

        # --- CASO C: SUCESSO ---
        if not driver.find_elements(By.ID, "login-user"):
            log("✅ Login realizado com sucesso!", "success")
            return True


def execute_generic_flow(driver, df, descricao_base, numero_chamado, usuario, senha, log, kb_function):

    # -----------------------------------------------------------
    # PARTE 1: NAVEGAÇÃO ATÉ O CHAMADO PAI
    # -----------------------------------------------------------

    if not _fazer_login(driver, usuario, senha, log):
        return  # Login falhou após todas as tentativas

    # Montar URL e navegar para o chamado PAI
    id_final = _normalizar_id_assyst(numero_chamado)
    url_chamado = _URL_CHAMADO.format(id_final=id_final)

    log(f"Navegando para o chamado PAI: {numero_chamado} (ID interno: {id_final})", type_log="status")
    driver.execute_script(f"window.location.href = '{url_chamado}';")
    time.sleep(2)

    try:
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "btlogEvent"))
        )
        log("Chamado PAI carregado com sucesso!", type_log="success")
    except Exception:
        log("Reforçando carregamento...", type_log="info")
        driver.refresh()
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.ID, "btlogEvent"))
            )
            log("Chamado PAI carregado apos refresh.", type_log="success")
        except Exception as e:
            log(f"Chamado PAI nao carregou em 30s. {e}", type_log="error")
            return

    # -----------------------------------------------------------
    # PARTE 2: FLUXO DO SUPER-LOOP (CRIAR CHAMADOS FILHOS)
    # -----------------------------------------------------------

    log("--- INICIANDO CRIAÇÃO DOS CHAMADOS FILHOS ---", type_log="status")

    for index, row in df.iterrows():

        detalhes_do_item = []

        for col, valor in row.items():
            if pd.notna(valor) and str(valor).strip() != '':
                detalhes_do_item.append(f"{col}: {valor}")

        detalhes_formatados = " | ".join(detalhes_do_item)
        description_son = f"{descricao_base}\n\n{detalhes_formatados}"

        log(f"--- Processando Linha {index + 1}/{len(df)}: {detalhes_formatados} ---", type_log="status")

        time.sleep(1)

        # -- DUPLICAR --
        try:
            botao_duplicar = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.ID, "btlogAsNewEvent"))
            )
            botao_duplicar.click()
            log("✅ Clicado em 'Salvar como novo'.", type_log="success")
        except Exception as e:
            log(f"❌ Erro ao clicar no botão 'Salvar como novo': {e}", type_log="error")

        time.sleep(1)

        # --- CONTINUAR ---
        try:
            xpath_continuar_flexivel = "//span[text()='Continuar']/ancestor::span[contains(@role, 'button')]"
            time.sleep(0.5)
            botao_continuar = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, xpath_continuar_flexivel)))
            driver.execute_script("arguments[0].click();", botao_continuar)
            log("✅ Clicado em 'Continuar'. Novo chamado filho carregado.", type_log="success")
            time.sleep(2)
        except Exception as e:
            log(f"❌ Erro TOTAL ao clicar no botão 'Continuar': {e}", type_log="error")
            raise Exception(f"Falha fatal ao clicar em 'Continuar': {e}")

        # -- PREENCHIMENTO DA DESCRIÇÃO (CKEDITOR) --
        try:
            iframe = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//iframe[contains(@title, 'rtES3_formattedRemarks')]"))
            )
            driver.switch_to.frame(iframe)
            corpo_editor = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body.cke_editable"))
            )
            corpo_editor.clear()
            corpo_editor.send_keys(description_son)
            driver.switch_to.default_content()
            log("✅ Descrição do chamado filho preenchida.", type_log="success")
        except Exception as e:
            log(f"❌ Erro ao preencher a descrição: {e}", type_log="error")

        # -- SALVAR --
        try:
            botao_salvar = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.ID, "btlogEvent")))
            botao_salvar.click()
            log("✅ Chamado salvo com sucesso.", type_log="success")
            time.sleep(2)
        except Exception as e:
            log(f"❌ Erro ao clicar no botão Salvar: {e}", type_log="error")
            raise Exception(f"Falha fatal ao salvar o chamado filho: {e}")

        # 2ª Ocorrência do BK: Chamando a função de KB específica (passada pelo app.py)
        log(f"Adicionando Base de Conhecimento", type_log="status")
        kb_function(driver, log)

    log("✅ Fim do processamento de todos os chamados.", type_log="success")