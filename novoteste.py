from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time

# --- CONFIGURAÇÃO INICIAL ---

# Use Raw String (r"...") ou barras normais (/) para evitar o erro de unicode escape no Windows.
# ⚠️ ATENÇÃO: Substitua pelo caminho correto do seu ChromeDriver!
CHROME_DRIVER_PATH = r"/home/velta-int-sys/Projects/Automatic/chromedriver-linux64/chromedriver" 
# Se estiver no Linux como no seu código anterior:
# CHROME_DRIVER_PATH = "/home/velta-int-sys/Projects/Automatic/chromedriver-linux64/chromedriver" 


def testar_base_conhecimento_windows():
    """
    Testa a pesquisa na Base de Conhecimento (BK) com a palavra-chave 'windowspe'
    e seleciona o segundo artigo ('rowId2').
    """
    
    # --- 1. SOLICITA O LINK ---
    link_site = input("Por favor, insira o link do Assyst (ex: https://cati.tjce.jus.br/...): ").strip()
    if not link_site:
        print("❌ Link do Assyst não fornecido. Encerrando.")
        return

    # --- 2. CONFIGURA O NAVEGADOR ---
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    # Mantém o navegador aberto após o script, para inspeção
    chrome_options.add_experimental_option("detach", True) 
    
    try:
        service = Service(CHROME_DRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        print(f"❌ Erro ao iniciar o ChromeDriver: Verifique se o caminho '{CHROME_DRIVER_PATH}' está correto e o driver está na versão certa. Erro: {e}")
        return

    # --- 3. INICIA E FAZ LOGIN MANUAL ---
    driver.get(link_site)
    print("⚙️ Navegador aberto. Por favor, faça login manualmente no Assyst...")

    # Espera até o menu de "Requisição de Serviço" aparecer, indicando que o login foi concluído.
    WebDriverWait(driver, 600).until(
        EC.presence_of_element_located((By.XPATH, "//span[contains(@class,'dijitTreeLabel') and text()='Requisição de Serviço']"))
    )
    print("✅ Login detectado! Iniciando testes de BK...")

    # A lógica abaixo assume que você já tem um chamado aberto na tela! 
    # Se não tiver, você precisa adicionar a lógica de abertura e preenchimento de chamado.

    # ----------------------------------------------------------------------
    # TESTE DA BASE DE CONHECIMENTO
    # ----------------------------------------------------------------------

    # -- PESQUISAR (Abre o modal da BK) -- 
    try:
        conhecimento = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.ID, "knowledgeMenu")) 
        )
        conhecimento.click()
        print("✅ Clicado no botão/menu 'Conhecimento'.")
        time.sleep(3)
        
    except Exception as e:
        print(f"❌ Erro ao clicar no menu 'Conhecimento': {e}")
        return


    # -- PALAVRA-CHAVE --
    try:
        campo_bk = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "NONE_knowledgeProcedure_lookup_query"))
        )
        campo_bk.clear() 
        campo_bk.send_keys("windowspe")  # 🎯 TESTE: Palavra-chave 'windowspe'
        
        print("✅ Campo 'Palavra-chave' preenchido com 'windowspe'.")
    except Exception as e:
        print(f"❌ Erro ao preencher 'Palavra-chave BK': {e}")
        return


    # -- LUPA --
    try:    
        botao_pesquisar_bk = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.ID, "btSearch")) 
        )
        botao_pesquisar_bk.click()
        print("✅ Clicado no botão 'Pesquisar'.")
        time.sleep(4)
        
    except Exception as e:
        print(f"❌ Erro ao clicar no botão 'Pesquisar': {e}")
        return

    # -- BOTÃO DIREITO (SELEÇÃO DO SEGUNDO ARTIGO) -- 
    try:
        # 🎯 TESTE: Usando 'rowId2' para selecionar o segundo artigo
        linha_artigo = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'dojoxGridRow') and contains(@class, 'rowId2')]")) 
        )
        actions = ActionChains(driver)
        actions.context_click(linha_artigo).perform()
        
        print("\n🎉 SUCESSO! Artigo da Base de Conhecimento (rowId2) selecionado com sucesso.")
        print("Aguardando 5 segundos para inspeção visual...")
        time.sleep(5)
        
    except Exception as e:
        print(f"\n❌ FALHA! Erro ao selecionar o segundo artigo (rowId2). O artigo pode não ter sido encontrado ou o seletor está errado. Erro: {e}")
        time.sleep(5)

# --- EXECUÇÃO ---
if __name__ == '__main__':
    testar_base_conhecimento_windows()