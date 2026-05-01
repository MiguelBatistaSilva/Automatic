"""
services/flow_bc.py — Fluxo de adicao de Base de Conhecimento em chamados ja criados.
Recebe uma lista de numeros de chamados filhos e executa apenas a Fase 2 (BC).
A chave do checkpoint e derivada do primeiro filho da lista.
"""
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from services import locators
from services.checkpoint import (
    inicializar, marcar_concluido_linha,
    existe_pendente, status_linha,
    STATUS_PENDENTE, STATUS_CONCLUIDO,
)

_URL_HOME        = "https://cati.tjce.jus.br/assystweb/application.do"
_URL_CHAMADO     = (
    "https://cati.tjce.jus.br/assystweb/application.do"
    "#event%2FDisplayEvent.do%3Fdispatch%3DgetEvent"
    "%26checkJukeBoxSettings%3Dtrue%26eventId%3D{id_final}%26resultSet%3D"
)
_SESSAO_EXPIRADA = (By.CSS_SELECTOR, "ol.axios-logout-error")


def _chave_checkpoint(filhos: list[str]) -> str:
    """Gera a chave do checkpoint a partir do primeiro filho da lista."""
    return f"bc_{filhos[0].strip()}"


def _normalizar_id_assyst(numero: str) -> str:
    n = str(numero).strip().upper()
    if n.startswith("S2"):
        return "7" + n[2:]
    if n.startswith("R2"):
        return "7" + n[2:]
    if n.isdigit():
        return f"1{n}"
    return n


def _sessao_expirada(driver) -> bool:
    try:
        return len(driver.find_elements(*_SESSAO_EXPIRADA)) > 0
    except Exception:
        return False


def _fazer_login(driver, usuario: str, senha: str, log) -> bool:
    tentativa = 0
    while True:
        driver.get(_URL_HOME)
        try:
            WebDriverWait(driver, 7).until(
                EC.presence_of_element_located(locators.selector_username)
            )
        except Exception:
            log("Sessao ja ativa.", "info")
            return True

        tentativa += 1
        log(f"Realizando login (tentativa {tentativa})...", "status")
        driver.find_element(*locators.selector_username).clear()
        driver.find_element(*locators.selector_username).send_keys(usuario)
        driver.find_element(*locators.selector_password).clear()
        driver.find_element(*locators.selector_password).send_keys(senha)
        driver.find_element(*locators.selector_login).click()
        time.sleep(3)

        if driver.find_elements(*_SESSAO_EXPIRADA):
            log(f"Licencas em uso, tentando novamente... (tentativa {tentativa})", "error")
            continue

        log("Login realizado com sucesso.", "success")
        return True


def _navegar_para_chamado(driver, numero_chamado: str, log) -> bool:
    id_final = _normalizar_id_assyst(numero_chamado)
    url = _URL_CHAMADO.format(id_final=id_final)
    log(f"Navegando para o chamado: {numero_chamado}", "status")
    driver.execute_script(f"window.location.href = '{url}';")
    time.sleep(2)
    try:
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "btlogEvent"))
        )
        log("Chamado carregado!", "success")
        return True
    except Exception:
        log("Reforcando carregamento...", "info")
        driver.refresh()
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.ID, "btlogEvent"))
            )
            log("Chamado carregado apos refresh.", "success")
            return True
        except Exception as e:
            log(f"Chamado nao carregou: {e}", "error")
            return False


def _adicionar_bc(driver, log, kb_function) -> bool:
    try:
        kb_function(driver, log)
        return True
    except Exception as e:
        log(f"Erro ao adicionar BC: {e}", "error")
        return False


def execute_bc_flow(driver, filhos: list[str], usuario: str, senha: str,
                    log, kb_function, iniciar_do_zero: bool = False):
    """
    Fluxo BC: recebe lista de numeros de chamados filhos ja criados
    e adiciona a Base de Conhecimento em cada um.
    Checkpoint indexado pelo primeiro filho da lista.
    """
    filhos = [f.strip() for f in filhos if f.strip()]
    if not filhos:
        log("Nenhum chamado informado.", "error")
        return

    total = len(filhos)
    chave = _chave_checkpoint(filhos)

    # -----------------------------------------------------------
    # CHECKPOINT
    # -----------------------------------------------------------
    if iniciar_do_zero or not existe_pendente(chave):
        log("Inicializando checkpoint BC...", "info")
        inicializar(chave, total)
    else:
        concluidos = sum(1 for i in range(total) if status_linha(chave, i) == STATUS_CONCLUIDO)
        pendentes  = total - concluidos
        log(f"Retomando execucao BC: {concluidos} concluidas, {pendentes} pendentes.", "status")

    # -----------------------------------------------------------
    # LOGIN
    # -----------------------------------------------------------
    if not _fazer_login(driver, usuario, senha, log):
        return

    # -----------------------------------------------------------
    # LOOP PRINCIPAL
    # -----------------------------------------------------------
    log(f"--- INICIANDO PROCESSAMENTO BC ({total} chamados) ---", "status")

    for index, numero_filho in enumerate(filhos):

        st = status_linha(chave, index)

        if st == STATUS_CONCLUIDO:
            log(f"Chamado {index + 1}/{total} ({numero_filho}): ja concluido, pulando.", "info")
            continue

        log(f"--- Chamado {index + 1}/{total}: {numero_filho} ---", "status")

        # Verificar sessao
        if _sessao_expirada(driver):
            if not _fazer_login(driver, usuario, senha, log):
                return

        # Navegar para o chamado filho
        if not _navegar_para_chamado(driver, numero_filho, log):
            log(f"Nao foi possivel acessar {numero_filho}. Pulando.", "error")
            continue

        # Verificar sessao antes da BC
        if _sessao_expirada(driver):
            if not _fazer_login(driver, usuario, senha, log):
                return

        # Adicionar BC
        log("Adicionando Base de Conhecimento...", "status")
        bc_ok = _adicionar_bc(driver, log, kb_function)

        if bc_ok:
            marcar_concluido_linha(chave, index)
            log(f"Checkpoint: {numero_filho} marcado como CONCLUIDO.", "success")
        else:
            log(f"BC nao adicionada em {numero_filho}. Sera retentada na proxima execucao.", "error")

        # Verificar sessao apos BC
        if _sessao_expirada(driver):
            if not _fazer_login(driver, usuario, senha, log):
                return

    # -----------------------------------------------------------
    # RESUMO FINAL
    # -----------------------------------------------------------
    concluidos = sum(1 for i in range(total) if status_linha(chave, i) == STATUS_CONCLUIDO)
    pendentes  = total - concluidos

    if pendentes > 0:
        log(f"Execucao BC finalizada: {concluidos}/{total} concluidas. "
            f"{pendentes} pendentes — execute novamente para completar.", "status")
    else:
        log(f"Base de Conhecimento adicionada em todos os {total} chamados!", "success")