from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

url_requisicao_servico = "https://cati.tjce.jus.br/assystweb/application.do#event%2FLogChangeHandler.do%3Fdispatch%3DprepareChange%26ncAction%3DCLEARHISTORY%26entRef%3DES3"

# Opções do Chrome (maximizar e manter aberto)
CHROME_OPTIONS = Options()
CHROME_OPTIONS.add_argument("--start-maximized")
CHROME_OPTIONS.add_experimental_option("detach", True)

def iniciar_driver_e_navegar(url_destino=url_requisicao_servico):
    """
    Inicializa o ChromeDriver (usando webdriver-manager) e navega para
    a URL de destino fornecida.
    """
    try:
        # Inicialização do Service com a portabilidade do webdriver-manager
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=CHROME_OPTIONS)

        # Navega para a URL de destino (Requisição de Serviço ou outra)
        driver.get(url_destino)

        print(f"✅ Driver iniciado. Navegando para: {url_destino}")

        return driver

    except Exception as e:
        print(f"❌ Erro ao iniciar ou navegar com o Driver: {e}")
        return None