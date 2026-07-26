"""
services/kb_manager_pw.py — Adicao de Base de Conhecimento em Playwright.

Portado do antigo `services/kb_manager.py` (Selenium, ja removido). Mesma sequencia
e mesmos seletores; so muda a API (page em vez de driver). E a parte mais
delicada da migracao: a
grade de artigos e um Dojo Grid VIRTUALIZADO (so renderiza as linhas visiveis),
por isso ainda e preciso rolar a caixa ate a linha do artigo entrar no DOM.

Diferenca de robustez frente ao Selenium: em vez de guardar a referencia da
linha achada (que o Dojo reciclava ao rolar), miramos a linha por TEXTO com
`filter(has_text=...)`, que e re-resolvido no momento do clique.

Em falha, LEVANTA excecao — o chamador (fluxo) marca a linha como nao-concluida.
Isso respeita a regra de "sinais reais" do checkpoint (ver kb_manager antigo).
"""

from playwright.sync_api import TimeoutError as PWTimeout

_SEL_MENU_KB = "#knowledgeMenu"
_SEL_CAMPO_BUSCA = "#NONE_knowledgeProcedure_lookup_query"
_SEL_BOTAO_BUSCA = "#btSearch"
_SEL_OVERLAY = "#contentOverlay"
_SEL_SCROLLBOX = ".dojoxGridScrollbox"
_SEL_LINHA = ".dojoxGridRow"
_SEL_ITEM_ACAO = "xpath=//td[contains(text(), 'Ação de Solução de Conhecimento')]/ancestor::tr[1]"
_SEL_SALVAR = "[id='ManageActionForm.btSave']"  # id com ponto -> seletor por atributo
_SEL_VOLTAR = "xpath=//span[text()='Voltar ao evento']/ancestor::span[contains(@role, 'button')]"
_SEL_BTLOG_EVENT = "#btlogEvent"

_MAX_SCROLLS = 15


def executar_kb_unica_pw(page, log, config):
    keyword = config.get("keyword")
    nome_artigo = config.get("nome_artigo")

    try:
        # 1. Abrir o menu de Base de Conhecimento e pesquisar
        page.click(_SEL_MENU_KB, timeout=15000)

        campo = page.locator(_SEL_CAMPO_BUSCA)
        campo.wait_for(state="visible", timeout=15000)
        campo.fill(keyword)
        page.click(_SEL_BOTAO_BUSCA)
        log(f"🔎 Pesquisando por: {keyword}", "status")

        # 2. Aguardar o overlay de carregamento sumir (bloqueia a leitura da grade)
        log("⏳ Aguardando resultados...", "status")
        page.locator(_SEL_OVERLAY).wait_for(state="hidden", timeout=20000)

        # 3. Localizar o artigo, rolando a grade Dojo virtualizada ate ele
        #    entrar no DOM. O alvo e mirado por TEXTO (re-resolvido no clique).
        log(f"🎯 Iniciando busca dinâmica por: {nome_artigo}", "status")
        page.locator(_SEL_SCROLLBOX).wait_for(state="visible", timeout=20000)
        artigo = page.locator(_SEL_LINHA).filter(has_text=nome_artigo).first

        encontrado = False
        for tentativa in range(_MAX_SCROLLS):
            if artigo.count() > 0:
                encontrado = True
                break
            log(f"⏳ Artigo não visível, rolando tabela... (página {tentativa + 1})", "info")
            page.eval_on_selector(_SEL_SCROLLBOX, "el => el.scrollTop += 200")
            page.wait_for_timeout(1000)  # tempo para o Dojo desenhar as novas linhas

        if not encontrado:
            raise Exception(f"❌ O artigo '{nome_artigo}' não foi encontrado após percorrer a tabela.")

        log("✅ Artigo localizado!", "status")
        artigo.scroll_into_view_if_needed()
        artigo.click(button="right")  # menu de contexto
        page.wait_for_timeout(900)

        # 4. Selecionar a acao no menu de contexto e salvar
        page.click(_SEL_ITEM_ACAO, timeout=10000)
        page.click(_SEL_SALVAR, timeout=10000)

        # 5. Voltar ao evento (botao custom do Dojo; clique via dispatch_event,
        #    equivalente ao execute_script('click') do Selenium)
        page.locator(_SEL_OVERLAY).wait_for(state="hidden", timeout=20000)
        voltar = page.locator(_SEL_VOLTAR)
        voltar.wait_for(state="attached", timeout=15000)
        voltar.dispatch_event("click")
        page.locator(_SEL_BTLOG_EVENT).wait_for(state="visible", timeout=15000)

        log(f"✨ Base aplicada: {nome_artigo}", "success")

    except Exception as e:
        log(f"❌ Erro na base {keyword}: {str(e)}", "error")
        raise
