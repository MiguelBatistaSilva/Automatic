from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time
from services import locators
from services.checkpoint import (
    inicializar, marcar_salvo, marcar_concluido_linha,
    existe_pendente, status_linha, numero_filho,
    STATUS_PENDENTE, STATUS_SALVO, STATUS_CONCLUIDO,
)

_URL_HOME    = "https://cati.tjce.jus.br/assystweb/application.do"
_URL_CHAMADO = (
    "https://cati.tjce.jus.br/assystweb/application.do"
    "#event%2FDisplayEvent.do%3Fdispatch%3DgetEvent"
    "%26checkJukeBoxSettings%3Dtrue%26eventId%3D{id_final}%26resultSet%3D"
)
_SESSAO_EXPIRADA = (By.CSS_SELECTOR, "ol.axios-logout-error")


def _normalizar_id_assyst(numero: str) -> str:
    n = str(numero).strip().upper()
    if n.startswith("S2"):
        return n.replace("S2", "7")
    if n.startswith("R"):
        return n.replace("R2", "7")
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
        log("Reforçando carregamento...", "info")
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


def _relogin(driver, numero_chamado, usuario, senha, log) -> bool:
    log("Sessao expirada! Reconectando...", "error")
    if not _fazer_login(driver, usuario, senha, log):
        return False
    return _navegar_para_chamado(driver, numero_chamado, log)


def _capturar_numero_filho(driver, log) -> str:
    """Captura o numero do chamado filho gerado pelo Assyst apos salvar."""
    try:
        titulo = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h1#contentPaneTitle"))
        ).text
        numero = titulo.split(" ")[0].strip()
        log(f"Numero do chamado filho capturado: {numero}", "info")
        return numero
    except Exception as e:
        log(f"Nao foi possivel capturar numero do filho: {e}", "error")
        return ""


def _adicionar_bc(driver, log, kb_function) -> bool:
    """Executa a funcao de KB e retorna True se sucesso."""
    try:
        kb_function(driver, log)
        return True
    except Exception as e:
        log(f"Erro ao adicionar BC: {e}", "error")
        return False


def execute_generic_flow(driver, df, descricao_base, numero_chamado,
                         usuario, senha, log, kb_function,
                         iniciar_do_zero: bool = False):

    total = len(df)
    numero_chamado = numero_chamado.strip()

    # -----------------------------------------------------------
    # CHECKPOINT — inicializar ou retomar
    # -----------------------------------------------------------
    if iniciar_do_zero or not existe_pendente(numero_chamado):
        log("Inicializando checkpoint...", "info")
        inicializar(numero_chamado, total)
    else:
        salvos    = sum(1 for i in range(total) if status_linha(numero_chamado, i) == STATUS_SALVO)
        concluidos = sum(1 for i in range(total) if status_linha(numero_chamado, i) == STATUS_CONCLUIDO)
        log(f"Retomando execucao: {concluidos} concluidas, {salvos} salvas sem BC, "
            f"{total - concluidos - salvos} pendentes.", "status")

    # -----------------------------------------------------------
    # LOGIN E NAVEGACAO
    # -----------------------------------------------------------
    if not _fazer_login(driver, usuario, senha, log):
        return

    if not _navegar_para_chamado(driver, numero_chamado, log):
        return

    # -----------------------------------------------------------
    # LOOP PRINCIPAL
    # -----------------------------------------------------------
    log(f"--- INICIANDO PROCESSAMENTO ({total} linhas) ---", "status")

    for index, row in df.iterrows():

        st = status_linha(numero_chamado, index)

        # Linha ja totalmente concluida — pular
        if st == STATUS_CONCLUIDO:
            log(f"Linha {index + 1}/{total}: ja concluida, pulando.", "info")
            continue

        log(f"--- Linha {index + 1}/{total} | status: {st} ---", "status")

        # Verificar sessao
        if _sessao_expirada(driver):
            if not _relogin(driver, numero_chamado, usuario, senha, log):
                return

        # Montar descricao
        detalhes = " | ".join(
            f"{col}: {valor}" for col, valor in row.items()
            if pd.notna(valor) and str(valor).strip()
        )
        description_son = f"{descricao_base}\n\n{detalhes}"

        # -----------------------------------------------------------
        # FASE 1: CRIAR E SALVAR O CHAMADO
        # Executar apenas se a linha ainda estiver pendente
        # Se ja estiver "salvo", pular direto para a BC
        # -----------------------------------------------------------
        if st == STATUS_PENDENTE:

            # -- DUPLICAR --
            try:
                botao = WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable((By.ID, "btlogAsNewEvent"))
                )
                botao.click()
                log("Clicado em 'Salvar como novo'.", "success")
            except Exception as e:
                if _sessao_expirada(driver):
                    if not _relogin(driver, numero_chamado, usuario, senha, log):
                        return
                    try:
                        botao = WebDriverWait(driver, 20).until(
                            EC.element_to_be_clickable((By.ID, "btlogAsNewEvent"))
                        )
                        botao.click()
                    except Exception as e2:
                        log(f"Erro ao duplicar: {e2}", "error")
                        continue
                else:
                    log(f"Erro ao duplicar: {e}", "error")
                    continue

            time.sleep(1)

            # -- CONTINUAR --
            try:
                xpath = "//span[text()='Continuar']/ancestor::span[contains(@role, 'button')]"
                time.sleep(0.5)
                botao = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, xpath))
                )
                driver.execute_script("arguments[0].click();", botao)
                log("Clicado em 'Continuar'.", "success")
                time.sleep(2)
            except Exception as e:
                log(f"Erro ao clicar em 'Continuar': {e}", "error")
                raise Exception(f"Falha fatal: {e}")

            # -- DESCRICAO --
            try:
                iframe = WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//iframe[contains(@title, 'rtES3_formattedRemarks')]")
                    )
                )
                driver.switch_to.frame(iframe)
                corpo = WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "body.cke_editable"))
                )
                corpo.clear()
                corpo.send_keys(description_son)
                driver.switch_to.default_content()
                log("Descricao preenchida.", "success")
            except Exception as e:
                driver.switch_to.default_content()
                log(f"Erro ao preencher descricao: {e}", "error")

            # -- SALVAR --
            try:
                botao = WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable((By.ID, "btlogEvent"))
                )
                botao.click()
                log("Chamado salvo.", "success")
                time.sleep(2)
            except Exception as e:
                log(f"Erro ao salvar: {e}", "error")
                raise Exception(f"Falha fatal: {e}")

            # Capturar numero do chamado filho gerado
            num_filho = _capturar_numero_filho(driver, log)

            # Marcar como SALVO com numero do filho
            marcar_salvo(numero_chamado, index, numero_filho=num_filho)
            log(f"Checkpoint: linha {index + 1} marcada como SALVA. Filho: {num_filho}", "info")

        else:
            # Linha ja salva — navegar para o chamado filho para adicionar BC
            num_filho = numero_filho(numero_chamado, index)
            if num_filho:
                log(f"Linha {index + 1} ja salva. Navegando para o filho {num_filho}...", "status")
                if not _navegar_para_chamado(driver, num_filho, log):
                    log(f"Nao foi possivel acessar o chamado filho {num_filho}.", "error")
                    continue
            else:
                log(f"Linha {index + 1} salva mas numero do filho nao encontrado. Pulando.", "error")
                continue

        # -----------------------------------------------------------
        # FASE 2: ADICIONAR BASE DE CONHECIMENTO
        # -----------------------------------------------------------

        # Verificar sessao antes da BC
        if _sessao_expirada(driver):
            if not _relogin(driver, numero_chamado, usuario, senha, log):
                return

        log("Adicionando Base de Conhecimento...", "status")
        bc_ok = _adicionar_bc(driver, log, kb_function)

        if bc_ok:
            # Marcar como CONCLUIDO — chamado + BC
            marcar_concluido_linha(numero_chamado, index)
            log(f"Checkpoint: linha {index + 1} marcada como CONCLUIDA.", "success")
        else:
            log(f"BC nao adicionada na linha {index + 1}. Sera retentada na proxima execucao.", "error")

        # Verificar sessao apos BC
        if _sessao_expirada(driver):
            if not _relogin(driver, numero_chamado, usuario, senha, log):
                return

    # Resumo final
    concluidos = sum(1 for i in range(total) if status_linha(numero_chamado, i) == STATUS_CONCLUIDO)
    salvos     = sum(1 for i in range(total) if status_linha(numero_chamado, i) == STATUS_SALVO)

    if salvos > 0:
        log(f"Execucao finalizada: {concluidos}/{total} concluidas. "
            f"{salvos} salvas sem BC — execute novamente para completar.", "status")
    else:
        log(f"Todos os {total} chamados processados com sucesso!", "success")