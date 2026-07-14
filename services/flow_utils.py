from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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
        # Aguarda ate 7s o campo de usuario renderizar. Se ele aparecer, ha tela
        # de login a preencher. Se estourar o timeout (campo nunca aparece), a
        # sessao ja esta ativa. NAO checar instantaneamente: a pagina pode ainda
        # nao ter renderizado o campo no milissegundo da checagem, o que faria o
        # login concluir "sessao ativa" por engano e travar o fluxo (corrida).
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


def _preencher_descricao(driver, log, descricao: str) -> bool:
    """
    Insere o conteúdo no CKEditor DIGITANDO via send_keys (como a mão humana).

    Digitar atualiza o MODELO interno do CKEditor, ao contrário do innerHTML —
    por isso a descrição herdada (quando o chamado e duplicado) e sobrescrita de
    forma limpa, sem "grudar" e repetir na cadeia. Antes de digitar, foca o editor
    e apaga o conteúdo herdado (Ctrl+A + Delete). Cada quebra de linha (\\n) vira
    um Enter no editor. Recebe TEXTO PURO (nao HTML).
    """
    try:
        # 1. Aguarda e localiza o iframe do CKEditor
        iframe = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(
                (By.XPATH, "//iframe[contains(@title, 'formattedRemarks')]")
            )
        )
        driver.switch_to.frame(iframe)

        # 2. Aguarda o corpo editável estar pronto
        corpo_editor = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body.cke_editable"))
        )

        # 3. Foca e limpa o conteúdo herdado
        corpo_editor.click()
        corpo_editor.send_keys(Keys.CONTROL, "a")
        corpo_editor.send_keys(Keys.DELETE)

        # 4. Digita linha a linha; cada \n vira um Enter no editor
        linhas = descricao.split("\n")
        for i, linha in enumerate(linhas):
            if i > 0:
                corpo_editor.send_keys(Keys.ENTER)
            if linha:
                corpo_editor.send_keys(linha)

        # Retorna para o escopo principal da página
        driver.switch_to.default_content()
        log("Descricao preenchida com sucesso.", "success")
        return True
    except Exception as e:
        log(f"Erro ao preencher descricao: {e}", "error")
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
