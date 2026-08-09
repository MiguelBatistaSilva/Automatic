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

ONDE FICA A FRONTEIRA DO FRACASSO: no clique em 'Salvar'. Antes dele, qualquer
erro e "base nao aplicada" e sobe como excecao. DEPOIS dele a base ja esta no
chamado, e nada pode ser reportado como falha — senao o checkpoint fica pendente
e a execucao seguinte aplica A MESMA BASE outra vez no mesmo chamado. Por isso a
confirmacao (passo 5) e o 'Voltar ao evento' (passo 6) vivem FORA do try.
A excecao `BaseAplicadaSemRetorno` e o meio-termo dessa regra: a base ESTA no
chamado e so a volta a tela do evento falhou.
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


class BaseAplicadaSemRetorno(Exception):
    """A base FOI salva no chamado, mas nao deu para voltar a tela do evento.

    Precisa ser distinta de uma falha comum: quem chama tem que contar a base
    como APLICADA (senao a proxima execucao aplicaria a MESMA base outra vez no
    mesmo chamado) e apenas reconstruir a navegacao por conta propria.
    """


def executar_kb_unica_pw(page, log, config, voltar_ao_evento: bool = True):
    """Aplica uma Base de Conhecimento no chamado que estiver aberto na tela.

    `voltar_ao_evento=False` encerra assim que a base e salva, deixando a tela na
    pesquisa de conhecimento. E o que o modo "So Base" quer: ele navega para
    OUTRO chamado em seguida, entao voltar ao evento era um clique a mais numa
    tela que ia ser descartada — e era justamente ali que o fluxo travava.
    """
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
        #    `.first`: o locator do Playwright e STRICT — se a tela tiver mais de
        #    um overlay, `wait_for` levantaria em vez de esperar o primeiro.
        log("⏳ Aguardando resultados...", "status")
        page.locator(_SEL_OVERLAY).first.wait_for(state="hidden", timeout=20000)

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

        # 4. Selecionar a acao no menu de contexto e salvar.
        #    O clique em Salvar e A FRONTEIRA: dali em diante a base ESTA no
        #    chamado (o formulario da acao nao tem campo a validar — e so
        #    "aplique este artigo"), entao ele e o ultimo passo que pode ser
        #    reportado como "base nao aplicada".
        page.click(_SEL_ITEM_ACAO, timeout=10000)
        page.click(_SEL_SALVAR, timeout=10000)

    except Exception as e:
        log(f"❌ Erro na base {keyword}: {str(e)}", "error")
        raise

    # 5. CONFIRMACAO — FORA do try acima, e NAO-FATAL de proposito.
    #
    # BUG QUE ISTO CONSERTA: aqui havia uma espera de ate 20s pelo overlay de
    # carregamento sumir, DENTRO do try acima — contradizendo o comentario que o
    # proprio passo trazia. Quando o overlay nao descia no tempo, a base ja
    # aplicada virava "❌ Erro na base": o fluxo gastava os 20s parados (o "fica
    # travado e depois navega"), o checkpoint NAO marcava concluido, e a
    # execucao seguinte aplicava A MESMA BASE OUTRA VEZ no mesmo chamado.
    #
    # O sinal agora e o botao Salvar SAIR da tela — o Assyst fecha o
    # ManageActionForm ao aceitar a acao. E o mesmo criterio ja provado em
    # producao no flow_atendimento_pw (pop-up que fecha) e no 'Continuar' do
    # Desmembramento: "sumiu" e observavel; "o overlay desceu" e um efeito
    # colateral que pode nem acontecer.
    try:
        page.locator(_SEL_SALVAR).first.wait_for(state="hidden", timeout=10000)
    except Exception:
        # Nao e falha: e falta de confirmacao. Fica registrado para quem for
        # conferir o chamado, sem derrubar a linha.
        log(f"⚠️ Base salva em '{nome_artigo}', mas o formulario da acao "
            "continuou na tela — confira o chamado se algo parecer fora do lugar.",
            "info")

    log(f"✨ Base aplicada: {nome_artigo}", "success")

    # 6. Voltar ao evento (botao custom do Dojo; clique via dispatch_event,
    #    equivalente ao execute_script('click') do Selenium). Fora do try acima
    #    DE PROPOSITO: a base ja esta aplicada, entao falhar aqui nao e "erro na
    #    base" — e so a tela que ficou no lugar errado.
    if not voltar_ao_evento:
        return

    try:
        voltar = page.locator(_SEL_VOLTAR)
        voltar.wait_for(state="attached", timeout=15000)
        voltar.dispatch_event("click")
        page.locator(_SEL_BTLOG_EVENT).wait_for(state="visible", timeout=15000)
    except Exception as e:
        raise BaseAplicadaSemRetorno(str(e)) from e
