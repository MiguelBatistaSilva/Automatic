from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import bk_windows
import time

def flow_windows(df, secretaria, link_site, log):

    # --- Configuração do Chrome ---
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        log(f"❌ Erro ao iniciar o ChromeDriver: Verifique a instalação do Chrome. Detalhe: {e}", "error")
        return

    # --- Acessa o Assyst ---
    driver.get(link_site)
    log(f"Acessando: {link_site}", "info")
    log("Aguardando login manual no Assyst...", "info")

    # Espera até o botão "Salvar" aparecer, indicando que o chamado carregou
    WebDriverWait(driver, 60).until(
        EC.presence_of_element_located((By.ID, "btlogEvent")) 
    )
    log("✅ Chamado Pai carregado com sucesso! Iniciando aplicação da Base de Conhecimento.")

    bk_windows.knowledgebase(driver)

    # -----------------------------------------------------------
    # FLUXO DO SUPER-LOOP
    # -----------------------------------------------------------

    # -- LOOOPING --

    log("--- INICIANDO CRIAÇÃO DOS CHAMADOS FILHOS ---", tipo="status")

    for index, row in df.iterrows():
        description_son = (f"Solicito atualização do sistema para Windows 11 no micro da {secretaria}:\n\n"
                        f"{row['MARCA/MODELO']} | Tombo: {row['TOMBO ANTIGO']}/{row['TOMBO NOVO']} | Nome: {row['NOME']}")
        
        log(f"Inserindo micro {row['MARCA/MODELO']} - Tombo: {row['TOMBO NOVO']}")

        # -- DUPLICAR --
        try:
            botao_duplicar = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.ID, "btlogAsNewEvent")) 
            )
            
            botao_duplicar.click()
            
            print("✅ Clicado em 'Salvar como novo'.") 
            
        except Exception as e:
            print(f"❌ Erro ao clicar no botão 'Salvar como novo': {e}")

        time.sleep(0.8)

        # -- CONTINUAR --
        try:

            xpath_continuar_flexivel = "//span[text()='Continuar']/ancestor::span[contains(@role, 'button')]"
            time.sleep(0.5)
            
            botao_continuar = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, xpath_continuar_flexivel)))

            driver.execute_script("arguments[0].click();", botao_continuar)

            print("✅ Clicado em 'Continuar' (XPath Global Flexível). Novo chamado filho carregado.")
            time.sleep(2)
            
        except Exception as e:
            print(f"❌ Erro TOTAL ao clicar no botão 'Continuar' (Falha na Flexibilidade): {e}")
            raise Exception(f"Falha fatal ao clicar em 'Continuar': {e}") # Interrompe o loop

        try:
            # Espera o iframe do CKEditor aparecer
            iframe = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//iframe[contains(@title, 'rtES3_formattedRemarks')]"))
            )

            # Entra no iframe do editor
            driver.switch_to.frame(iframe)

            # Localiza o corpo editável
            corpo_editor = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body.cke_editable"))
            )

            # Insere o texto no campo
            corpo_editor.clear()
            corpo_editor.send_keys(description_son)

            # Volta ao contexto principal
            driver.switch_to.default_content()

        except Exception as e:
            print("❌ Erro ao preencher a descrição:", e)

        # -- SALVAR --
        try:
            botao_salvar = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.ID, "btlogEvent")))
            
            botao_salvar.click()
            
            print("✅ Chamado salvo com sucesso (clique no disquete)")
            time.sleep(2) 
            
        except Exception as e:
            print(f"❌ Erro ao clicar no botão Salvar: {e}")

        log(f"Adicionando Base de Conhecimento", tipo="status")

        bk_windows.knowledgebase(driver)