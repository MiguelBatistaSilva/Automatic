"""
Script de teste: insere a descrição via send_keys (DIGITANDO) sem salvar o chamado.

Uso:
    python teste_descricao.py

Objetivo deste teste: validar se inserir a descrição DIGITANDO (send_keys) —
em vez de injetar innerHTML — reproduz corretamente o texto e as quebras de linha.
Digitar atualiza o MODELO interno do CKEditor (como a mão humana), o que na teoria
mata o bug da descrição repetida na origem. Aqui NÃO salvamos nada — só conferimos
visualmente se o texto (com a linha em branco no meio) cai certo no editor.

O script vai:
  1. Fazer login
  2. Navegar para o chamado-pai informado
  3. Clicar em "Salvar como novo"
  4. Clicar em "Continuar"
  5. Inserir a descrição via send_keys (limpando o herdado antes)
  6. PAUSAR — aguarda ENTER antes de fechar (não salva nada)
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from services.driver_manager import DriverManager
from services.flow_utils import _fazer_login, _navegar_para_chamado

# Descrição real de exemplo (com linha em branco no meio) para testar a quebra.
DESCRICAO_PADRAO_TESTE = (
    "Solicito a baixa de imagem do COMPUTADOR de tombo: 111111 para GALPAO, "
    "em PPA123 ao COMPUTADOR de tombo: 222222.\n\n"
    "NOMENCLATURA: T20GALPBR + 111111."
)

USUARIO        = input("Usuário: ").strip()
SENHA          = input("Senha: ").strip()
NUMERO_CHAMADO = input("Número do chamado-pai (ex: S2123456): ").strip()
_desc_in = input(
    "Texto da descrição em UMA linha (Enter para usar o exemplo multi-linha padrão): "
).strip()
DESCRICAO_TESTE = _desc_in if _desc_in else DESCRICAO_PADRAO_TESTE


def log(msg, nivel="info"):
    prefixos = {"info": "[INFO]", "status": "[STATUS]", "success": "[OK]", "error": "[ERRO]"}
    print(f"{prefixos.get(nivel, '[?]')} {msg}")


def _preencher_descricao_sendkeys(driver, log, texto: str) -> bool:
    """
    Insere a descrição no CKEditor DIGITANDO via send_keys (como a mão humana).

    Diferente do innerHTML, digitar atualiza o modelo interno do CKEditor, então
    a descrição herdada é sobrescrita de forma limpa. Antes de digitar, foca o
    editor e apaga o conteúdo herdado (Ctrl+A + Delete). As quebras de linha do
    texto (\\n) viram Enter no editor.
    """
    try:
        # 1. Localiza e entra no iframe do CKEditor
        iframe = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(
                (By.XPATH, "//iframe[contains(@title, 'formattedRemarks')]")
            )
        )
        driver.switch_to.frame(iframe)

        # 2. Aguarda o corpo editável
        corpo_editor = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body.cke_editable"))
        )

        # 3. Foca e limpa o conteúdo herdado
        corpo_editor.click()
        corpo_editor.send_keys(Keys.CONTROL, "a")
        corpo_editor.send_keys(Keys.DELETE)

        # 4. Digita linha a linha; cada \n vira um Enter no editor
        linhas = texto.split("\n")
        for i, linha in enumerate(linhas):
            if i > 0:
                corpo_editor.send_keys(Keys.ENTER)
            if linha:
                corpo_editor.send_keys(linha)

        driver.switch_to.default_content()
        log("Descricao preenchida via send_keys.", "success")
        return True
    except Exception as e:
        log(f"Erro ao preencher descricao (send_keys): {e}", "error")
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
        return False


def main():
    dm = DriverManager(log)

    try:
        log("Iniciando Chrome...", "status")
        driver = dm.iniciar_driver_e_navegar()

        if not _fazer_login(driver, USUARIO, SENHA, log):
            log("Login falhou. Encerrando.", "error")
            return

        if not _navegar_para_chamado(driver, NUMERO_CHAMADO, log):
            log("Não foi possível carregar o chamado. Encerrando.", "error")
            return

        # Clicar em "Salvar como novo"
        try:
            botao = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.ID, "btlogAsNewEvent"))
            )
            botao.click()
            log("Clicado em 'Salvar como novo'.", "success")
        except Exception as e:
            log(f"Erro ao clicar em 'Salvar como novo': {e}", "error")
            return

        time.sleep(1)

        # Clicar em "Continuar"
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
            return

        # Inserir descrição via send_keys (DIGITANDO)
        log("─" * 50, "info")
        log("TESTANDO INSERÇÃO DA DESCRIÇÃO VIA send_keys...", "status")
        log("─" * 50, "info")

        ok = _preencher_descricao_sendkeys(driver, log, DESCRICAO_TESTE)

        log("─" * 50, "info")
        if ok:
            log("RESULTADO: descrição digitada com sucesso!", "success")
        else:
            log("RESULTADO: falha ao digitar a descrição. Veja os logs acima.", "error")
        log("─" * 50, "info")
        log("Confira no browser se o texto e a quebra de linha ficaram certos.", "info")
        log("O chamado NÃO será salvo.", "info")

        input("\n>>> Pressione ENTER para encerrar o Chrome <<<\n")

    finally:
        dm.encerrar_driver()


if __name__ == "__main__":
    main()
