from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time

def knowledgebase(driver):
    
    # -- PESQUISAR -- 
    try:
        conhecimento = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.ID, "knowledgeMenu")) 
        )
        conhecimento.click()
        
        print("✅ Clicado no botão/menu 'Conhecimento'.")
        
    except Exception as e:
        print(f"❌ Erro ao clicar no menu 'Conhecimento': {e}")

    time.sleep(3)

    # -- PALAVRA-CHAVE --
    try:
        campo_bk = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "NONE_knowledgeProcedure_lookup_query"))
        )
        
        campo_bk.clear() 
        campo_bk.send_keys("itom") 
        
        print("✅ Campo 'Palavra-chave' preenchido e limpo.")

    except Exception as e:
        print(f"❌ Erro ao preencher 'Palavra-chave BK': {e}")

    # -- LUPA --
    try:    
        botao_pesquisar_bk = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.ID, "btSearch")) 
        )
        
        botao_pesquisar_bk.click()
        
        print("✅ Clicado no botão 'Pesquisar'.")
        
    except Exception as e:
        print(f"❌ Erro ao clicar no botão 'Pesquisar': {e}")

    time.sleep(3)

    # -- PROCURANDO... --
    try:
        cabecalho_classificacao = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "knowledgeSearch_shownValues_gridHdr1"))
        )
        
        actions = ActionChains(driver)
        actions.double_click(cabecalho_classificacao).perform()
        
        print("✅ Reordenação da tabela concluída.")
        
    except Exception as e:
        print(f"❌ Erro ao reordenar a tabela: {e}")

    time.sleep(1)

    # -- BOTÃO DIREITO -- 
    try:
        linha_artigo = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'dojoxGridRow') and contains(@class, 'rowId1')]")) 
        )
        
        actions = ActionChains(driver)
        actions.context_click(linha_artigo).perform()
        
        print("✅ Artigo da Base de Conhecimento selecionado.")
        time.sleep(1)
        
    except Exception as e:
        print(f"❌ Erro ao selecionar o artigo da Base de Conhecimento: {e}")

    # -- AÇÃO DE SOLUÇÃO --
    try:
        xpath_menu_item = "//td[contains(text(), 'Ação de Solução de Conhecimento')]/ancestor::tr[1]"

        acao_solucao_pai = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, xpath_menu_item)) 
        )
        
        acao_solucao_pai.click()
        print("✅ Clicado em 'Ação de Solução de Conhecimento' (XPATH do Pai).")
        time.sleep(2) 
        
    except Exception as e:
        print(f"❌ Erro ao clicar na 'Ação de Solução de Conhecimento' (XPATH do Pai): {e}")

    # -- SALVAR AÇÃO -- 
    try:    
        botao_salvar_acao = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.ID, "ManageActionForm.btSave")) 
        )
        
        botao_salvar_acao.click()
        
        print("✅ Ação de Solução de Conhecimento salva e confirmada.")
        time.sleep(2) 
        
    except Exception as e:
        print(f"❌ Erro ao clicar no botão 'Salvar ação': {e}")

    # -- SAIR --
    xpath_voltar = "//span[text()='Voltar ao evento']/ancestor::span[contains(@role, 'button')]"

    try:
        botao_voltar = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, xpath_voltar)) 
        )
        
        # Tenta clicar com o Selenium, e se falhar, usa JS como fallback
        try:
            botao_voltar.click()
        except:
            driver.execute_script("arguments[0].click();", botao_voltar)
        
        print("✅ Retorno à tela do Chamado concluído (usando texto 'Voltar ao evento').")

    except Exception as e:
        print(f"❌ Erro ao clicar no botão 'Voltar ao evento' (XPATH): {e}")