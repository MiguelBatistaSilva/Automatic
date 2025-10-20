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
# Usando o formato antigo de inputs (se estiver testando este arquivo separado)
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
driver.get("https://cati.tjce.jus.br/assystweb/application.do")

print("⚙️ Faça login manualmente no Assyst...")

WebDriverWait(driver, 600).until(
    EC.presence_of_element_located((By.XPATH, "//span[contains(@class,'dijitTreeLabel') and text()='Requisição de Serviço']"))
)
print("✅ Login detectado!")

# 3. Expande possíveis menus pais antes do clique
try:
    menu_element = driver.find_element(By.XPATH, "//span[contains(@class,'dijitTreeLabel') and text()='Requisição de Serviço']")
    
    driver.execute_script("arguments[0].scrollIntoView(true);", menu_element)
    
    driver.execute_script("arguments[0].click();", menu_element)
    
    print("✅ Clicou em 'Requisição de Serviço'")
    
except Exception as e:
    print("❌ Erro ao clicar:", e)

# === USUÁRIO ===

try:
    usuario = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.ID, "ManageEventForm_ES3_affectedUser_textNode"))
    )
    usuario.click()
    usuario.send_keys("400566")
    time.sleep(1)

    # Pressiona seta para baixo + enter
    usuario.send_keys(u'\ue015')  # ↓
    usuario.send_keys(u'\ue007')  # Enter
    print("✅ Campo 'Usuário Afetado' preenchido com sucesso!")

except Exception as e:
    print("❌ Erro ao preencher 'Usuário Afetado':", e)

time.sleep(0.8)

# === RESUMO ===

try:
    resumo = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.ID,"ManageEventForm_ES3_shortDescription"))
    )
    resumo.send_keys("Instalação do Itom")
    print("✅ Campo 'Título do Chamado' preenchido com sucesso.")

except Exception as e:
    print("❌ Erro ao preencher o título do chamado:", e)

# --- DESCRIÇÃO ---
descricao = f"Solicito instalação do Itom nos micros da {secretaria}:\n\n"

for _, row in df.iterrows():
    descricao += f"- {row['MARCA/MODELO']} | Tombo: {row['TOMBO ANTIGO']}/{row['TOMBO NOVO']} | Nome: {row['NOME']}\n"

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
    corpo_editor.send_keys(descricao)

    # Volta ao contexto principal
    driver.switch_to.default_content()

    print(f"✅ Campo 'Descrição' preenchido com traços ({len(df)} micros).")

except Exception as e:
    print("❌ Erro ao preencher a descrição:", e)

time.sleep(0.8)

# --- PPRODUTO ---
try:
    produto = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.ID, "ManageEventForm_ES3_itemAProduct_textNode"))
    )
    produto.click()
    produto.clear()
    produto.send_keys("Software")
    time.sleep(0.8) 
    produto.send_keys(u'\ue015')  
    produto.send_keys(u'\ue007')  
    print("✅ Campo 'Produto' preenchido com 'Software'")
except Exception as e:
    print("❌ Erro ao preencher 'Produto':", e)

time.sleep(0.8)

# --- ITEM ---
try:
    item = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.ID, "ManageEventForm_ES3_itemA_textNode"))
    )
    item.click()
    item.send_keys("Software e Aplicativos")
    time.sleep(0.8)  
    item.send_keys(u'\ue015') 
    item.send_keys(u'\ue007')
    print("✅ Campo 'Item' preenchido com 'Software e Aplicativos'")
except Exception as e:
    print("❌ Erro ao preencher 'Item':", e)

time.sleep(0.8)

# --- PRODUTO B ---
try:
    item = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.ID, "ManageEventForm_ES3_itemBProduct_textNode"))
    )
    item.click()
    item.send_keys("A ser definido") 
    time.sleep(0.8)  
    item.send_keys(u'\ue015') 
    item.send_keys(u'\ue007') 
    print("✅ Campo 'Produto B' preenchido com 'A ser definido'")

except Exception as e:
    print("❌ Erro ao preencher 'Produto B':", e)

time.sleep(0.9)

# --- ITEM B ---
try:
    item = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.ID, "ManageEventForm_ES3_itemB_textNode"))
    )
    item.click()
    item.send_keys("IC NÃO LOCALIZADO") 
    time.sleep(0.8)  
    item.send_keys(u'\ue015') 
    item.send_keys(u'\ue007') 
    print("✅ Campo 'Item B' preenchido com 'IC NÃO LOCALIZADO'")

except Exception as e:
    print("❌ Erro ao preencher 'Item B':", e)

time.sleep(0.8)

# --- CATEGORIA ---
try:
    item = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.ID, "ManageEventForm_ES3_eventBuilder_textNode"))
    )
    item.click()
    item.send_keys("Instalação") 
    time.sleep(0.8)  
    item.send_keys(u'\ue015') 
    item.send_keys(u'\ue007') 
    print("✅ Campo 'Categoria' preenchido com 'Instalação'")
except Exception as e:
    print("❌ Erro ao preencher 'Categoria':", e)

time.sleep(0.8)

# -- Grupo de Serv. Atribuído --
try:
    service_group = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.ID, "ManageEventForm_ES3_assignedServDept_textNode"))
    )
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", service_group)
    service_group.clear() 

    service_group.send_keys("2N CATI FCB")
    time.sleep(0.8) 
    service_group.send_keys(u'\ue015')  # Seta para Baixo (Down Arrow)
    service_group.send_keys(u'\ue007')  # Enter
    
    print("✅ Campo 'Grupo de Serv. Atribuído' limpo com sucesso.")

except Exception as e:
    print(f"❌ Erro ao rolar ou limpar 'Grupo de Serv. Atribuído': {e}")

time.sleep(1)

# --- USUÁRIO ATRIBUÍDO ---
try:
    usuario_atribuido_element = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "ManageEventForm_ES3_assignee_textNode"))
        )
        
    usuario_atribuido_element.clear()
    usuario_atribuido_element.send_keys("Miguel Batista da Silva")
    time.sleep(0.9)
    usuario_atribuido_element.send_keys(u'\ue015') # Seta para Baixo
    usuario_atribuido_element.send_keys(u'\ue007') # Enter
        
    print("✅ Campo 'Usuário Atribuído' preenchido e selecionado.")

except Exception as e:
    print(f"❌ Erro ao preencher 'Usuário Atribuído': {e}")



print("\n✅ AUTOMAÇÃO CONCLUÍDA. NAVEGADOR ABERTO PARA ANÁLISE.")
try:
    # Pausa a execução no console. Pressione ENTER para fechar.
    input("Pressione ENTER para fechar o navegador e finalizar o script...")
except EOFError:
    pass
except KeyboardInterrupt:
    # Trata Ctrl+C durante a pausa, fechando o navegador
    pass
    
# Fecha o navegador
if 'driver' in locals() or 'driver' in globals():
    driver.quit()
    print("Navegador encerrado.")
