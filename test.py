from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
#from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
import time

# --- CONFIGURAÇÃO INICIAL ---

# Link de login do Assyst (Fixo)
ASSYST_URL = "https://cati.tjce.jus.br/assystweb/application.do"
# ID do Iframe do menu (Assumido pelo padrão)
IFRAME_MENU_ID = "LeftFrame"

# ----------------------------------------------------------------------
# FUNÇÃO DE CLIQUE OTIMIZADA (Baseada no HTML do menu que você forneceu)
# ----------------------------------------------------------------------
def clicar_no_menu_item(driver, texto_item, tempo_espera=5):
    """
    Procura o elemento do menu baseado no atributo 'title' e no texto, e clica no rótulo.
    """
    # XPATH: Encontra a div que tem o title exato E o span com o texto exato.
    xpath_seletor = (
        f"//div[@title='{texto_item}' and contains(@class, 'dijitTreeRow')]"
        f"//span[contains(@class,'dijitTreeLabel') and text()='{texto_item}']"
    )

    try:
        item = WebDriverWait(driver, tempo_espera).until(
            EC.element_to_be_clickable((By.XPATH, xpath_seletor))
        )

        item.click()
        print(f"   -> Menu '{texto_item}' clicado com sucesso.")
        time.sleep(1)  # Pausa para a animação/carregamento do menu
        return True

    except Exception as e:
        print(f"   ❌ NÃO ENCONTRADO/CLICÁVEL: '{texto_item}'.")
        return False


def testar_navegacao_assyst_servico():
    """
    Testa a navegação manual de login, seguida pela navegação automática
    até "Requisição de Serviço".
    """

    # --- 1. CONFIGURA O NAVEGADOR ---
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_experimental_option("detach", True)

    try:
        # Se você está usando o caminho fixo, descomente as linhas abaixo
        # service = Service(CHROME_DRIVER_PATH)
        # driver = webdriver.Chrome(service=service, options=chrome_options)

        # Usando webdriver_manager (RECOMENDADO para evitar problemas de caminho/versão)
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

    except Exception as e:
        print(f"❌ Erro ao iniciar o ChromeDriver. Erro: {e}")
        return

    # --- 2. INICIA E FAZ LOGIN MANUAL ---
    driver.get(ASSYST_URL)
    print("⚙️ Navegador aberto. Por favor, faça login manualmente no Assyst...")

    try:
        # Espera que o elemento de sucesso (o botão 'Início' ou a estrutura do menu) apareça
        # O elemento 'Início' aparece no corpo principal (não no iframe)
        WebDriverWait(driver, 600).until(
            EC.presence_of_element_located((By.XPATH, "//span[contains(text(),'Início')]"))
        )
        print("\n✅ LOGIN MANUAL DETECTADO! Iniciando navegação automática...")

        # 3. MUDANÇA DE FOCO PARA IFRAME (CRÍTICO)
        WebDriverWait(driver, 10).until(
            EC.frame_to_be_available_and_switch_to_it((By.NAME, IFRAME_MENU_ID))
        )
        print(f"✅ Foco alterado para o iframe: {IFRAME_MENU_ID}")

        # 4. NAVEGAÇÃO SEQUENCIAL NO MENU
        print("\n⚙️ Iniciando cliques: Requisição -> Registrar requisição -> Requisição de Serviço")

        # Sequência de cliques baseada no seu HTML
        if not clicar_no_menu_item(driver, "Requisição"): return
        if not clicar_no_menu_item(driver, "Registrar requisição"): return

        # CLIQUE FINAL (Requisição de Serviço)
        if clicar_no_menu_item(driver, "Requisição de Serviço"):
            print("=======================================================")
            print("🎉 SUCESSO! ACESSO AO FORMULÁRIO DE REQUISIÇÃO.")
            print("=======================================================")
        else:
            print("❌ FALHA: Não foi possível clicar no link final 'Requisição de Serviço'.")

        # 5. VOLTAR FOCO (Opcional, mas boa prática)
        driver.switch_to.default_content()
        print("✅ Foco retornado. Fim da execução do script.")

    except TimeoutException:
        print("\n❌ TEMPO ESGOTADO (10 minutos): O login manual não foi detectado.")

    except Exception as e:
        print(f"\nOcorreu um erro geral durante a execução: {e}")

    # O navegador permanece aberto devido ao 'detach=True'