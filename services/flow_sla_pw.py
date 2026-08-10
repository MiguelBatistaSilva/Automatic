"""
Extracao do historico de acoes em Playwright.

Portado do antigo `services/flow_sla.py` (Selenium, ja removido). A logica de
extracao e os indices de coluna sao os mesmos; so muda a API para `page`.
"""

from services.browser_pw import _fazer_login_pw, _navegar_para_chamado_pw

# `except Exception` largo de proposito — ver a mesma nota em
# flow_atendimento_pw.py: capturar so PWTimeout deixava erros de strict mode e
# de elemento desprendido derrubarem a lista inteira de chamados.

_SEL_EXPANDER = "[id='event.tabs.actions_titleDiv']"
_SEL_LINHAS = ".dojoxGridRow.actionGridRow"

# Le a grade inteira em UMA ida ao navegador, em vez de uma chamada por celula
# (eram 8 por linha no fluxo Selenium). Os indices de coluna e o innerText sao
# os mesmos do flow_sla.py, para o resultado bater com o do fluxo antigo.
_JS_EXTRAIR_LINHAS = """
(linhas) => linhas.map(linha => {
    const celulas = linha.querySelectorAll('td.dojoxGridCell');
    if (celulas.length < 8) return null;
    const texto = el => (el ? el.innerText.trim() : '');
    return {
        tipo:             texto(celulas[2]),
        data:             texto(celulas[3]),
        autor:            texto(celulas[4]),
        depto_autor:      texto(celulas[5]),
        atribuido_a:      texto(celulas[6]),
        depto_atribuido:  texto(celulas[7]),
        descricao:        texto(linha.querySelector('.actionremarksbody')),
    };
}).filter(item => item !== null)
"""


def extrair_historico(page, numero_chamado: str, usuario: str, senha: str, log) -> list | None:
    """
    Faz login, navega para o chamado e extrai o historico de acoes.
    Retorna a lista de dicts com os dados de cada acao, ou None em caso de falha.
    """
    if not _fazer_login_pw(page, usuario, senha, log):
        return None

    return extrair_historico_chamado(page, numero_chamado, log)


def extrair_historico_chamado(page, numero_chamado: str, log) -> list | None:
    """
    Navega para o chamado e extrai o historico de acoes, assumindo que o login
    ja foi feito (sessao ativa). Pensado para processar uma lista de chamados
    reaproveitando a mesma pagina sem relogar a cada um.
    Retorna a lista de dicts com os dados de cada acao, ou None em caso de falha.
    """
    if not _navegar_para_chamado_pw(page, numero_chamado, log):
        return None

    # Expande o painel "Historico de Acoes"
    try:
        expander = page.locator(_SEL_EXPANDER)
        expander.wait_for(state="visible", timeout=15000)
        expander.click()
        log("Histórico de ações aberto.", "status")
    except Exception as e:
        log(f"Nao foi possível abrir o histórico de ações: {e}", "error")
        return None

    # No fluxo Selenium havia um sleep(3) fixo aqui; agora espera-se a primeira
    # linha da grade aparecer de fato — mais rapido quando o painel abre logo e
    # mais seguro quando o Assyst demora mais que 3s.
    try:
        page.locator(_SEL_LINHAS).first.wait_for(state="attached", timeout=15000)
    except Exception:
        log("Nenhuma ação encontrada no histórico.", "error")
        return None

    historico = page.eval_on_selector_all(_SEL_LINHAS, _JS_EXTRAIR_LINHAS)
    if not historico:
        log("Nenhuma ação encontrada no histórico.", "error")
        return None

    log(f"{len(historico)} ações extraídas do histórico.", "success")
    return historico
