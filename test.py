from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time

# --- CONFIGURAÇÃO INICIAL ---

# Palavra-chave e texto esperado para TESTE
# ⚠️ Substitua 'itom' e o texto do artigo para cada cenário que você quer testar!
PALAVRA_CHAVE_TESTE = "nomenclatura"
TEXTO_ESPERADO_NO_ARTIGO = "BC - Nomenclaturas dos Microcomputadores do Tribunal de Justiça do Estado do Ceará"
ID_CABECALHO_CLASSIFICACAO = "knowledgeSearch_shownValues_gridHdr1"

# ----------------------------------------------------------------------
# FUNÇÃO CENTRAL DE TESTE DA BASE DE CONHECIMENTO
# ----------------------------------------------------------------------
def testar_base_conhecimento_com_validacao():
    # --- 1. SOLICITA O LINK ---
    link_site = input("Por favor, insira o link do chamado/Assyst (ex: https://cati.tjce.jus.br/...): ").strip()
    if not link_site:
        print("❌ Link do Assyst não fornecido. Encerrando.")
        return

    # --- 2. CONFIGURA O NAVEGADOR (Com Portabilidade) ---
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_experimental_option("detach", True)  # Mantém aberto para inspeção

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        print(f"❌ Erro ao iniciar o ChromeDriver: {e}")
        return

    # --- 3. INICIA E FAZ LOGIN MANUAL ---
    driver.get(link_site)
    print("⚙️ Navegador aberto. Por favor, faça login e carregue o chamado manualmente...")

    # Espera até o botão "Salvar" (btlogEvent) aparecer, indicando que o chamado carregou.
    try:
        WebDriverWait(driver, 600).until(
            EC.presence_of_element_located((By.ID, "btlogEvent"))
        )
        print("✅ Chamado carregado! Iniciando teste de BK...")
    except TimeoutException:
        print("❌ Tempo limite esgotado (10 minutos). Chamado não detectado. Encerrando.")
        driver.quit()
        return

    # ----------------------------------------------------------------------
    # FLUXO DA BASE DE CONHECIMENTO
    # ----------------------------------------------------------------------

    # -- A. ABRIR BK --
    try:
        conhecimento = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.ID, "knowledgeMenu"))
        )
        conhecimento.click()
        print("✅ Clicado no botão/menu 'Conhecimento'.")
        # Espera o campo de Palavra-chave aparecer no modal
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "NONE_knowledgeProcedure_lookup_query"))
        )
    except Exception as e:
        print(f"❌ FALHA na A: Erro ao abrir BK: {e}")
        return

    # -- B. PESQUISAR --
    try:
        campo_bk = driver.find_element(By.ID, "NONE_knowledgeProcedure_lookup_query")
        campo_bk.clear()
        campo_bk.send_keys(PALAVRA_CHAVE_TESTE)

        botao_pesquisar_bk = driver.find_element(By.ID, "btSearch")
        botao_pesquisar_bk.click()
        print(f"✅ Pesquisa por '{PALAVRA_CHAVE_TESTE}' iniciada.")

        # Espera a primeira linha da tabela de resultados carregar
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(
                (By.XPATH, "//div[contains(@class, 'dojoxGridRow') and contains(@class, 'rowId0')]"))
        )

    except Exception as e:
        print(f"❌ FALHA na B: Erro na pesquisa da BK: {e}")
        return

    # -- C. REORDENAR A TABELA (Double Click no Cabeçalho) --
    try:
        cabecalho_classificacao = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "knowledgeSearch_shownValues_gridHdr1"))
        )

        actions = ActionChains(driver)
        actions.double_click(cabecalho_classificacao).perform()

        print("✅ Reordenação da tabela concluída.")

    except Exception as e:
        print(f"❌ Erro ao reordenar a tabela: {e}")

    # -- C. VALIDAÇÃO DO ARTIGO (NOVO PASSO CRÍTICO) --
    try:
        # XPATH para pegar o texto da célula na coluna do título/resumo da linha rowId1 (Segundo Artigo)
        # O seletor exato da coluna pode variar (geralmente é a segunda ou terceira célula)
        # Vamos tentar o XPath genérico para a linha e pegar o texto da linha inteira
        # rowId2 é a terceira
        xpath_linha_validacao = "//div[contains(@class, 'dojoxGridRow') and contains(@class, 'rowId1')]"
        linha_artigo_element = driver.find_element(By.XPATH, xpath_linha_validacao)

        # Pega o texto de TODAS as colunas da linha
        texto_completo_da_linha = linha_artigo_element.text

        if TEXTO_ESPERADO_NO_ARTIGO in texto_completo_da_linha:
            print("=========================================================")
            print(f"🎉 SUCESSO! O artigo correto foi encontrado na linha 'rowId1'.")
            print(f"   -> Texto esperado: '{TEXTO_ESPERADO_NO_ARTIGO}'")
            print("=========================================================")
        else:
            print("=========================================================")
            print(f"❌ FALHA NA VALIDAÇÃO! O artigo esperado NÃO foi encontrado.")
            print(f"   -> Palavra-chave: '{PALAVRA_CHAVE_TESTE}'")
            print(f"   -> Texto esperado: '{TEXTO_ESPERADO_NO_ARTIGO}'")
            print(f"   -> Texto encontrado na linha 'rowId1': '{texto_completo_da_linha}'")
            print("=========================================================")
            # Se a validação falhar, podemos parar aqui para inspeção
            return

    except Exception as e:
        print(f"❌ FALHA na C: Erro ao tentar validar o artigo 'rowId1'. O artigo pode não existir. Erro: {e}")
        return

    # -- D. APLICAÇÃO (Simulação do restante do fluxo) --
    try:
        # 1. Clique com o botão direito na linha validada (rowId1)
        actions = ActionChains(driver)
        actions.context_click(linha_artigo_element).perform()

        # 2. Espera o menu de contexto e clica em 'Ação de Solução de Conhecimento'
        xpath_menu_item = "//div[contains(@class, 'dijitMenuItem') and .//span[text()='Ação de Solução de Conhecimento']]"
        acao_solucao = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, xpath_menu_item))
        )
        acao_solucao.click()

        print("\n✅ Artigo selecionado e menu 'Ação de Solução' clicado.")
        time.sleep(5)  # Pausa para você inspecionar o resultado final

    except Exception as e:
        print(f"❌ FALHA na D: Erro ao aplicar a Base de Conhecimento: {e}")


# --- EXECUÇÃO ---
if __name__ == '__main__':
    testar_base_conhecimento_com_validacao()