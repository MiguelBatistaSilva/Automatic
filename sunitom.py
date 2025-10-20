from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import bk_itom
import pandas as pd
import time

# --- INPUTS INICIAIS ---
arquivo_excel = input("Caminho do arquivo Excel: ").strip()
secretaria = input("Nome da Secretaria: ").strip()

# --- Lê o Excel ---
df = pd.read_excel(arquivo_excel)

# --- Configuração do Chrome ---
chrome_options = Options()
chrome_options.add_argument("--start-maximized")

service = Service("/home/velta-int-sys/Projects/Automatic/chromedriver-linux64/chromedriver")  # coloque o caminho se necessário
driver = webdriver.Chrome(service=service, options=chrome_options)

# --- Acessa o Assyst ---
driver.get("https://cati.tjce.jus.br/assystweb/application.do#event%2FDisplayEvent.do%3Fdispatch%3DgetEvent%26checkJukeBoxSettings%3Dtrue%26eventId%3D7185994")

print("⚙️ Faça login manualmente no Assyst...")

WebDriverWait(driver, 600).until(
    EC.presence_of_element_located((By.XPATH, "//span[contains(@class,'dijitTreeLabel') and text()='Requisição de Serviço']"))
)
print("✅ Login detectado!")

for index, row in df.iterrows():
    description_son = (f"Solicito instalação do Itom no micro da {secretaria}:\n\n"
                      f"{row['MARCA/MODELO']} | Tombo: {row['TOMBO ANTIGO']}/{row['TOMBO NOVO']} | Nome: {row['NOME']}")
    
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
    
    # -- DESCRIÇÃO --

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
        time.sleep(3) 
        
    except Exception as e:
        print(f"❌ Erro ao clicar no botão Salvar: {e}")

    bk_itom.knowledgebase(driver)