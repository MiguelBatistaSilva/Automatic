from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import os
import time
from pathlib import Path
from services import locators

_URL_HOME = "https://cati.tjce.jus.br/assystweb/application.do"
_URL_CHAMADO = (
    "https://cati.tjce.jus.br/assystweb/application.do"
    "#event%2FDisplayEvent.do%3Fdispatch%3DgetEvent"
    "%26checkJukeBoxSettings%3Dtrue%26eventId%3D{id_final}%26resultSet%3D"
)
_SESSAO_EXPIRADA = (By.CSS_SELECTOR, "ol.axios-logout-error")
_FILHOS_DIR = Path(__file__).parent.parent / "data"


def _path_filhos(numero_chamado: str) -> Path:
    _FILHOS_DIR.mkdir(parents=True, exist_ok=True)
    nome = numero_chamado.strip().replace("/", "_").replace("\\", "_")
    return _FILHOS_DIR / f"filhos_{nome}.txt"


def _registrar_filho(numero_chamado: str, numero_filho_str: str) -> None:
    """Adiciona o numero do filho ao TXT, sem duplicatas."""
    if not numero_filho_str:
        return
    p = _path_filhos(numero_chamado)
    existentes = set()
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            existentes = {linha.strip() for linha in f if linha.strip()}
    if numero_filho_str.strip() not in existentes:
        with open(p, "a", encoding="utf-8") as f:
            f.write(numero_filho_str.strip() + "\n")


def _abrir_txt_filhos(numero_chamado: str) -> None:
    """Abre o TXT de filhos no Bloco de Notas se existir e tiver conteudo."""
    p = _path_filhos(numero_chamado)
    if p.exists() and p.stat().st_size > 0:
        os.startfile(str(p))


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


def _preencher_descricao(driver, log, html_descricao: str) -> bool:
    """
    Insere o HTML no CKEditor da descrição, descobrindo o nome da instância
    dinamicamente em vez de depender de um nome fixo que varia por sessão.
    Retorna True se a inserção foi confirmada.
    """
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "iframe.cke_wysiwyg_frame")
            )
        )
    except Exception as e:
        log(f"iframe do CKEditor nao encontrado: {e}", "error")
        return False

    time.sleep(0.5)

    # Descobre dinamicamente o nome da instancia que contem 'formattedRemarks'
    nome_instancia = driver.execute_script(
        "if (typeof CKEDITOR === 'undefined') return null;"
        "var keys = Object.keys(CKEDITOR.instances);"
        "return keys.find(function(k) { return k.indexOf('formattedRemarks') !== -1; }) || null;"
    )

    if nome_instancia:
        try:
            driver.execute_script(
                "CKEDITOR.instances[arguments[0]].setData(arguments[1]);",
                nome_instancia, html_descricao
            )
            log("Descricao preenchida.", "success")
            return True
        except Exception as e:
            log(f"Erro ao usar instancia CKEditor '{nome_instancia}': {e}", "error")

    # Fallback: injeta direto no body do iframe
    log("Instancia CKEditor nao encontrada; usando fallback no iframe.", "error")
    try:
        iframe = driver.find_element(By.CSS_SELECTOR, "iframe.cke_wysiwyg_frame")
        driver.switch_to.frame(iframe)
        body = driver.find_element(By.CSS_SELECTOR, "body.cke_editable")
        driver.execute_script("arguments[0].innerHTML = arguments[1];", body, html_descricao)
        driver.switch_to.default_content()
        log("Fallback: descricao injetada no body do iframe.", "success")
        return True
    except Exception as e:
        log(f"Fallback de descricao falhou: {e}", "error")
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
        return False


def _adicionar_bc(driver, log, kb_function) -> bool:
    """Executa a funcao de KB e retorna True se sucesso."""
    try:
        kb_function(driver, log)
        return True
    except Exception as e:
        log(f"Erro ao adicionar BC: {e}", "error")
        return False


def _montar_descricao(template: str, row) -> str:
    resultado = template
    for col, valor in row.items():
        marcador = "{{" + str(col) + "}}"
        valor_str = "" if pd.isna(valor) else str(valor).strip()
        resultado = resultado.replace(marcador, valor_str)
    return resultado
