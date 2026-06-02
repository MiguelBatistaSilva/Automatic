from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time

def executar_kb_unica(driver, log, config):

    keyword = config.get("keyword")
    nome_artigo = config.get("nome_artigo")

    try:
        WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.ID, "knowledgeMenu"))).click()

        time.sleep(3)

        campo = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "NONE_knowledgeProcedure_lookup_query")))
        campo.clear()
        campo.send_keys(keyword)
        driver.find_element(By.ID, "btSearch").click()

        log(f"🔎 Pesquisando por: {keyword}", "status")
        time.sleep(2)

        # AGUARDAR O SISTEMA PROCESSAR (O overlay bloqueia a leitura do texto)

        log("⏳ Aguardando resultados...", "status")
        WebDriverWait(driver, 20).until(EC.invisibility_of_element_located((By.ID, "contentOverlay")))
        time.sleep(1.5)

        # 3. LOCALIZAÇÃO DO ARTIGO
        log(f"🎯 Iniciando busca dinâmica por: {nome_artigo}", "status")

        # Localiza a caixa de scroll (o container que realmente rola)
        scroll_box = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".dojoxGridScrollbox"))
        )

        artigo_elemento = None
        tentativas_scroll = 0
        max_scrolls = 15

        while tentativas_scroll < max_scrolls:
            # 1. Tenta achar o artigo nas linhas atualmente visíveis no HTML
            linhas = driver.find_elements(By.CSS_SELECTOR, ".dojoxGridRow")
            for linha in linhas:
                # Usamos innerText para ignorar as tags <b> que vimos no seu HTML
                if nome_artigo.lower() in linha.get_attribute("innerText").lower():
                    artigo_elemento = linha
                    break

            if artigo_elemento:
                break  # Achamos!

            # 2. Se não achou, rola a caixa um pouco para baixo para carregar novas linhas
            log(f"⏳ Artigo não visível, rolando tabela... (página {tentativas_scroll + 1})", "info")
            driver.execute_script("arguments[0].scrollTop += 200;", scroll_box)
            time.sleep(1)  # Tempo para o Dojo Grid 'desenhar' as novas linhas
            tentativas_scroll += 1

        if artigo_elemento:
            log(f"✅ Artigo localizado!", "status")
            # Garante que ele está centralizado para o clique
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", artigo_elemento)
            time.sleep(0.5)

            # Clique com botão direito
            ActionChains(driver).context_click(artigo_elemento).perform()
            time.sleep(0.9)

        else:
            raise Exception(f"❌ O artigo '{nome_artigo}' não foi encontrado após percorrer a tabela.")

        # SELECIONAR AÇÃO E SALVAR
        xpath_menu_item = "//td[contains(text(), 'Ação de Solução de Conhecimento')]/ancestor::tr[1]"
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, xpath_menu_item))).click()
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "ManageActionForm.btSave"))).click()

        # VOLTAR
        WebDriverWait(driver, 20).until(EC.invisibility_of_element_located((By.ID, "contentOverlay")))
        xpath_voltar = "//span[text()='Voltar ao evento']/ancestor::span[contains(@role, 'button')]"
        btn_voltar = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.XPATH, xpath_voltar)))
        driver.execute_script("arguments[0].click();", btn_voltar)

        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "btlogEvent")))

        log(f"✨ Base aplicada: {nome_artigo}", "success")

    except Exception as e:
        log(f"❌ Erro na base {keyword}: {str(e)}", "error")
        raise