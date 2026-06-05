import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from services.flow_utils import _fazer_login, _navegar_para_chamado


def extrair_historico(driver, numero_chamado: str, usuario: str, senha: str, log) -> list | None:
    """
    Faz login, navega para o chamado e extrai o histórico de ações.
    Retorna a lista de dicts com os dados de cada ação, ou None em caso de falha.
    """
    if not _fazer_login(driver, usuario, senha, log):
        return None

    return extrair_historico_chamado(driver, numero_chamado, log)


def extrair_historico_chamado(driver, numero_chamado: str, log) -> list | None:
    """
    Navega para o chamado e extrai o histórico de ações, assumindo que o login
    já foi feito (sessão ativa). Pensado para processar uma lista de chamados
    reaproveitando o mesmo driver sem relogar a cada um.
    Retorna a lista de dicts com os dados de cada ação, ou None em caso de falha.
    """
    if not _navegar_para_chamado(driver, numero_chamado, log):
        return None

    # Expande o painel "Histórico de Ações"
    try:
        expander = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "event.tabs.actions_titleDiv"))
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", expander)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", expander)
        log("Historico de Acoes aberto.", "status")
        time.sleep(3)
    except Exception as e:
        log(f"Nao foi possivel abrir o Historico de Acoes: {e}", "error")
        return None

    # Coleta as linhas da grade de histórico
    linhas = driver.find_elements(By.CSS_SELECTOR, ".dojoxGridRow.actionGridRow")
    if not linhas:
        log("Nenhuma acao encontrada no historico.", "error")
        return None

    historico = []
    for linha in linhas:
        try:
            celulas = linha.find_elements(By.CSS_SELECTOR, "td.dojoxGridCell")
            if len(celulas) < 8:
                continue
            historico.append({
                "tipo":           celulas[2].get_attribute("innerText").strip(),
                "data":           celulas[3].get_attribute("innerText").strip(),
                "autor":          celulas[4].get_attribute("innerText").strip(),
                "depto_autor":    celulas[5].get_attribute("innerText").strip(),
                "atribuido_a":    celulas[6].get_attribute("innerText").strip(),
                "depto_atribuido":celulas[7].get_attribute("innerText").strip(),
                "descricao":      linha.find_element(By.CLASS_NAME, "actionremarksbody")
                                      .get_attribute("innerText").strip(),
            })
        except Exception:
            continue

    log(f"{len(historico)} acoes extraidas do historico.", "success")
    return historico
