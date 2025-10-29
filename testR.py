from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
import time

# --- CONFIGURAÇÃO E CONSTANTES ---

# Seletor do campo RESUMO (Usando o ID que você forneceu)
CAMPO_RESUMO_SELETOR = (By.ID, "ManageEventForm_ES3_shortDescription")
TEXTO_RESUMO = "TESTE AUTOMATIZADO: Preenchimento de Resumo BEM-SUCEDIDO."

# Seletor do campo USUÁRIO AFETADO (ID provável - CONFIRME NO SEU AMBIENTE)
CAMPO_USUARIO_SELETOR = (By.ID, "ManageEventForm_ES3_affectedUser_textNode")
NOME_USUARIO_AFETADO = "400566"  # <--- SUBSTITUA PELO NOME REAL PARA TESTE

# ----------------------------------------------------------------------
# LÓGICA DE EXECUÇÃO DO TESTE PRINCIPAL
# ----------------------------------------------------------------------
def testar_preenchimento_chamado():
    # --- 1. SOLICITA A URL FINAL ---
    link_requisicao_final = input("Por favor, insira a URL final da 'Requisição de Serviço': ").strip()

    if not link_requisicao_final:
        print("❌ URL não fornecida. Encerrando.")
        return

    # --- 2. CONFIGURA E INICIA O NAVEGADOR ---
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_experimental_option("detach", True)
    driver = None

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

        # Abre a URL da Requisição de Serviço
        driver.get(link_requisicao_final)

        print("\n⚙️ Navegador aberto. Por favor, faça login ou aguarde o carregamento do formulário...")

        # O tempo limite para esta espera inclui o tempo que você leva para fazer o login manual.
        # Esperamos o campo de USUÁRIO AFETADO (que é o primeiro a ser preenchido)
        print("\n⚙️ Esperando o formulário carregar (até 5 minutos para login e carregamento)...")

        # --- 3. ESPERAR CAMPO USUÁRIO E PREENCHER (PRIMEIRO) ---
        campo_usuario = WebDriverWait(driver, 300).until(
            EC.presence_of_element_located(CAMPO_USUARIO_SELETOR)
        )
        print("✅ Formulário carregado. Preenchendo o campo 'Usuário Afetado'...")
        # Removido .clear() conforme solicitado
        campo_usuario.send_keys(NOME_USUARIO_AFETADO)

        # --- 4. ESPERAR CAMPO RESUMO E PREENCHER (SEGUNDO) ---
        # Espera extra de 10 segundos apenas para garantir que o Resumo apareceu após o Usuário (se houver regra de negócio)
        print("✅ Preenchendo o campo 'Resumo'...")
        campo_resumo = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(CAMPO_RESUMO_SELETOR)
        )
        # Removido .clear() conforme solicitado
        campo_resumo.send_keys(TEXTO_RESUMO)

        print("===============================================================")
        print("🎉 SUCESSO! O TESTE DE FLUXO E PREENCHIMENTO INICIAL FOI BEM-SUCEDIDO.")
        print(f"   -> Campo 'Usuário Afetado' preenchido com: '{NOME_USUARIO_AFETADO}'")
        print(f"   -> Campo 'Resumo' preenchido com: '{TEXTO_RESUMO}'")
        print("===============================================================")

        time.sleep(10)  # Pausa para inspeção visual

    except TimeoutException:
        print("\n❌ FALHA CRÍTICA: Um dos campos não carregou a tempo. Por favor, verifique:")
        print("   1. Se a URL está correta e o login foi realizado.")
        print(f"   2. O ID do campo 'Usuário Afetado': {CAMPO_USUARIO_SELETOR}")
        print(f"   3. O ID do campo 'Resumo': {CAMPO_RESUMO_SELETOR}")
    except Exception as e:
        print(f"\nOcorreu um erro geral durante a execução do script: {e}")

    finally:
        if driver:
            print("\n✅ Script finalizado.")


# --- EXECUÇÃO ---
if __name__ == '__main__':
    testar_preenchimento_chamado()