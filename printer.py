from driver_manager import iniciar_driver_e_navegar
from selectors import *
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import bk_printer
import time

def flow_printer(df, secretaria, link_site, usuario_atribuido, log):

    log("Criando Requisição de Serviço...", tipo="status")

    # 1. --- INICIALIZAÇÃO E NAVEGAÇÃO CENTRALIZADA ---

    driver = iniciar_driver_e_navegar()
    if driver is None:
        log("❌ Falha na inicialização do Driver. Encerrando.", "error")
        return

    log("Aguardando login manual no Assyst...", "info")
    print("⚙️ Faça login manualmente no Assyst...")

    # 2. --- ESPERA PELA PÁGINA FINAL (Usando seletor centralizado) ---
    try:
        # Esperamos pelo campo USUARIO_AFETADO, que agora é a nossa chave de sincronização
        WebDriverWait(driver, 600).until(
            EC.presence_of_element_located(usuario_afetado)
        )
        print("✅ Login e Formulário detectados e carregados!")

    except TimeoutException:
        log("❌ Tempo esgotado (10 minutos). Login/Carregamento falhou.", "error")
        driver.quit()
        return
    except Exception as e:
        log(f"❌ Erro na detecção do formulário: {e}", "error")
        driver.quit()
        return

    # === USUÁRIO ===
    try:
        usuario = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(usuario_afetado)
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
            EC.presence_of_element_located(resumo_selector)
        )
        resumo.send_keys("Instalação de Impressora")
        print("✅ Campo 'Título do Chamado' preenchido com sucesso.")

    except Exception as e:
        print("❌ Erro ao preencher o título do chamado:", e)

    # --- DESCRIÇÃO ---
    descricao = f"Solicito instalação de Impressora nos micros da {secretaria}:\n\n"

    for _, row in df.iterrows():
        descricao += f"- {row['MARCA/MODELO']} | Tombo: {row['TOMBO ANTIGO']}/{row['TOMBO NOVO']} | Nome: {row['NOME']}\n"

    try:
        # Espera o iframe do CKEditor aparecer
        iframe = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(descricao_iframe)
        )

        # Entra no iframe do editor
        driver.switch_to.frame(iframe)

        # Localiza o corpo editável
        corpo_editor = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(descricao_body)
        )

        # Insere o texto no campo
        corpo_editor.clear()
        corpo_editor.send_keys(descricao)

        # Volta ao contexto principal
        driver.switch_to.default_content()

        print(f"✅ Campo 'Descrição' preenchido com traços ({len(df)} micros).")

    except Exception as e:
        print("❌ Erro ao preencher a descrição:", e)

    time.sleep(1)

    # --- PRODUTO ---
    try:
        produto = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(produto_selector)
        )
        produto.click()
        produto.clear()
        produto.send_keys("Serviço de Impressão e Digitalização")
        time.sleep(0.8)
        produto.send_keys(u'\ue015')
        produto.send_keys(u'\ue007')
        print("✅ Campo 'Produto' preenchido com 'Serviço de Impressão e Digitalização'")
    except Exception as e:
        print("❌ Erro ao preencher 'Produto':", e)

    time.sleep(0.8)

    # --- ITEM ---
    try:
        item = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(item_selector)
        )
        item.click()
        item.send_keys("Serviço de Impressão")
        time.sleep(0.8)
        item.send_keys(u'\ue015')
        item.send_keys(u'\ue007')
        print("✅ Campo 'Item' preenchido com 'Serviço de Impressão'")
    except Exception as e:
        print("❌ Erro ao preencher 'Item':", e)

    time.sleep(0.8)

    # --- PRODUTO B ---
    try:
        item = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(produto_b)
        )
        item.click()
        item.send_keys("Digitalização e Impressão")
        time.sleep(0.8)
        item.send_keys(u'\ue015')
        item.send_keys(u'\ue007')
        print("✅ Campo 'Produto B' preenchido com 'Digitalização e Impressão'")

    except Exception as e:
        print("❌ Erro ao preencher 'Produto B':", e)

    time.sleep(0.9)

    # --- ITEM B ---
    try:
        item = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(item_b)
        )
        item.click()
        item.send_keys("Impressoras")
        time.sleep(0.8)
        item.send_keys(u'\ue015')
        item.send_keys(u'\ue007')
        print("✅ Campo 'Item B' preenchido com 'Impressoras'")

    except Exception as e:
        print("❌ Erro ao preencher 'Item B':", e)

    time.sleep(0.8)

    # --- CATEGORIA ---
    try:
        item = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(categoria_selector)
        )
        item.click()
        item.send_keys("Configuração")
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
            EC.presence_of_element_located(grupo_atribuido)
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", service_group)

        service_group.clear()
        service_group.send_keys("2N CATI FCB")
        time.sleep(0.8)
        service_group.send_keys(u'\ue015')  # Seta para Baixo (Down Arrow)
        service_group.send_keys(u'\ue007')  # Enter

        print("✅ Campo 'Grupo de Serv. Atribuído' limpo e selecionado com sucesso.")

    except Exception as e:
        print(f"❌ Erro ao rolar ou limpar 'Grupo de Serv. Atribuído': {e}")

    time.sleep(1)

    # --- USUÁRIO ATRIBUÍDO ---
    try:
        usuario_atribuido_element = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(usuario_atribuido_selector)
        )

        usuario_atribuido_element.clear()
        usuario_atribuido_element.send_keys(usuario_atribuido)
        time.sleep(0.9)
        usuario_atribuido_element.send_keys(u'\ue015') # Seta para Baixo
        usuario_atribuido_element.send_keys(u'\ue007') # Enter

        print("✅ Campo 'Usuário Atribuído' preenchido e selecionado.")

    except Exception as e:
        print(f"❌ Erro ao preencher 'Usuário Atribuído': {e}")

    time.sleep(0.8)

    # -- SALVAR --
    try:
        botao_salvar = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable(disquete)
        )

        botao_salvar.click()
        print("✅ Chamado salvo com sucesso (clique no disquete)")
        time.sleep(4)

    except Exception as e:
        print(f"❌ Erro ao clicar no botão Salvar: {e}")

    log(f"Adicionando Base de Conhecimento", tipo="status")

    bk_printer.knowledgebase(driver)

    # -----------------------------------------------------------
    # FLUXO DO SUPER-LOOP
    # -----------------------------------------------------------

    # -- LOOOPING --

    log("Criando chamados remanescentes...", tipo="status")

    for index, row in df.iterrows():
        description_son = (f"Solicito instalação da impressora no micro da {secretaria}:\n\n"
                        f"{row['MARCA/MODELO']} | Tombo: {row['TOMBO ANTIGO']}/{row['TOMBO NOVO']} | Nome: {row['NOME']}")

        log(f"Inserindo micro {row['MARCA/MODELO']} - Tombo: {row['TOMBO NOVO']}")

        # -- DUPLICAR --
        try:
            botao_duplicar = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable(duplicar)
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
                EC.presence_of_element_located(descricao_iframe)
            )

            # Entra no iframe do editor
            driver.switch_to.frame(iframe)

            # Localiza o corpo editável
            corpo_editor = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located(descricao_body)
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
                EC.element_to_be_clickable(disquete))

            botao_salvar.click()

            print("✅ Chamado salvo com sucesso (clique no disquete)")
            time.sleep(2)

        except Exception as e:
            print(f"❌ Erro ao clicar no botão Salvar: {e}")

        log(f"Adicionando Base de Conhecimento", tipo="status")

        bk_printer.knowledgebase(driver)