import os
import sys
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options as ChromeOptions

# --- CAMINHOS BASE ---
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    BASE_PATH = sys._MEIPASS
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

DRIVERS_DIR = os.path.join(BASE_PATH, "driver")

CHROME_PROFILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "chrome_profile"))
if not os.path.exists(CHROME_PROFILE_PATH):
    os.makedirs(CHROME_PROFILE_PATH)


class DriverManager:
    def __init__(self, log_func):
        self.log = log_func
        self.driver = None

    def _get_driver_path(self) -> str:
        for root, _, files in os.walk(DRIVERS_DIR):
            if "chromedriver.exe" in files:
                return os.path.join(root, "chromedriver.exe")
        raise FileNotFoundError(f"chromedriver.exe nao encontrado em {DRIVERS_DIR}")

    def iniciar_driver_e_navegar(self):
        if self.driver:
            try:
                _ = self.driver.current_url
                return self.driver
            except Exception:
                self.driver = None

        try:
            driver_path = self._get_driver_path()
            self.log(f"Iniciando Chrome com driver: {driver_path}", "info")

            options = ChromeOptions()
            options.add_experimental_option("useAutomationExtension", False)
            options.add_experimental_option("detach", True)
            options.add_argument("--disable-infobars")
            options.add_argument("--disable-extensions")
            options.add_argument("--start-maximized")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            # options.add_argument(f"user-data-dir={CHROME_PROFILE_PATH}")
            options.add_experimental_option("excludeSwitches", ["enable-logging"])

            self.log("Iniciando webdriver.Chrome...", "info")
            service = Service(driver_path)
            self.driver = webdriver.Chrome(service=service, options=options)
            self.log("Chrome iniciado com sucesso.", "info")

            return self.driver

        except Exception as e:
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass
            self.driver = None
            self.log(f"DETALHE DO ERRO: {str(e)}", "error")
            raise RuntimeError(f"ERRO AO INICIAR O CHROME: {e}")

    def encerrar_driver(self):
        if self.driver:
            try:
                self.driver.quit()
                self.log("Sessao do WebDriver encerrada.", "info")
            except Exception as e:
                self.log(f"Erro ao encerrar driver: {e}", "error")
            finally:
                self.driver = None