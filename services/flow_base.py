from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from services.checkpoint import (
    inicializar, marcar_salvo, marcar_concluido_linha,
    existe_pendente, foi_concluido, status_linha, numero_filho,
    STATUS_PENDENTE, STATUS_SALVO, STATUS_CONCLUIDO,
)
from services.flow_utils import (
    _registrar_filho, _abrir_txt_filhos,
    _sessao_expirada, _fazer_login,
    _navegar_para_chamado, _relogin, _capturar_numero_filho,
    _montar_descricao, _adicionar_bc,
)


def execute_generic_flow(driver, df, descricao_base, numero_chamado,
                         usuario, senha, log, kb_function,
                         iniciar_do_zero: bool = False):

    total = len(df)
    numero_chamado = numero_chamado.strip()
    filhos_novos = []  # acumula filhos gerados nessa execucao

    # -----------------------------------------------------------
    # CHECKPOINT — inicializar ou retomar
    # -----------------------------------------------------------
    if iniciar_do_zero or (not existe_pendente(numero_chamado) and not foi_concluido(numero_chamado)):
        log("Inicializando checkpoint...", "info")
        inicializar(numero_chamado, total)
    else:
        salvos     = sum(1 for i in range(total) if status_linha(numero_chamado, i) == STATUS_SALVO)
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

        # Montar descricao substituindo marcadores {{COL}} pelo valor da linha
        description_son = _montar_descricao(descricao_base, row)

        # -----------------------------------------------------------
        # FASE 1: CRIAR E SALVAR O CHAMADO
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
                continue

            # -- DESCRICAO --
            # O titulo do iframe tem ID dinamico (rtEC119_, rtES3_, etc)
            # Usamos a classe fixa cke_wysiwyg_frame e rebuscamos antes
            # de switch_to para evitar stale element reference
            try:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "iframe.cke_wysiwyg_frame")
                    )
                )
                time.sleep(0.5)
                iframe = driver.find_element(By.CSS_SELECTOR, "iframe.cke_wysiwyg_frame")
                driver.switch_to.frame(iframe)
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "body.cke_editable"))
                )
                # Converter quebras de linha para HTML antes de injetar
                html_descricao = description_son.replace("\n\n", "</p><p>").replace("\n", "<br>")
                html_descricao = "<p>" + html_descricao + "</p>"
                driver.execute_script("""
                    var body = document.querySelector('body.cke_editable');
                    if (body) { body.innerHTML = arguments[0]; }
                """, html_descricao)
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
                continue

            # Capturar numero do chamado filho
            num_filho = _capturar_numero_filho(driver, log)

            # Registrar filho no TXT (acumulando)
            if num_filho:
                _registrar_filho(numero_chamado, num_filho)
                filhos_novos.append(num_filho)

            # Marcar como SALVO
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
        if _sessao_expirada(driver):
            if not _relogin(driver, numero_chamado, usuario, senha, log):
                return

        log("Adicionando Base de Conhecimento...", "status")
        bc_ok = _adicionar_bc(driver, log, kb_function)

        if bc_ok:
            marcar_concluido_linha(numero_chamado, index)
            log(f"Checkpoint: linha {index + 1} marcada como CONCLUIDA.", "success")
        else:
            log(f"BC nao adicionada na linha {index + 1}. Sera retentada na proxima execucao.", "error")

        if _sessao_expirada(driver):
            if not _relogin(driver, numero_chamado, usuario, senha, log):
                return

    # -----------------------------------------------------------
    # RESUMO FINAL
    # -----------------------------------------------------------
    concluidos = sum(1 for i in range(total) if status_linha(numero_chamado, i) == STATUS_CONCLUIDO)
    salvos     = sum(1 for i in range(total) if status_linha(numero_chamado, i) == STATUS_SALVO)

    if salvos > 0:
        log(f"Execucao finalizada: {concluidos}/{total} concluidas. "
            f"{salvos} salvas sem BC — execute novamente para completar.", "status")
    else:
        log(f"Todos os {total} chamados processados com sucesso!", "success")

    # Abrir TXT de filhos se gerou pelo menos um filho novo nessa execucao
    if filhos_novos:
        log(f"Abrindo arquivo de chamados filhos ({len(filhos_novos)} novos)...", "info")
        _abrir_txt_filhos(numero_chamado)

