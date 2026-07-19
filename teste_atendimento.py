"""
Script de teste: inicia o atendimento de um chamado em Atendimento Programado,
indo ate o preenchimento da descricao SEM clicar em 'Salvar acao'.

Uso:
    python teste_atendimento.py

O script vai:
  1. Fazer login
  2. Navegar para o chamado informado (deve estar em Atendimento Programado)
  3. Abrir Actions -> Clock Actions -> Atendimento Iniciado
  4. Preencher a descricao no pop-up (via _preencher_descricao)
  5. PARAR antes de 'Salvar acao' e aguardar ENTER (nao altera o chamado)

Se algum passo do menu falhar, entra em MODO CAPTURA: reabre o menu Actions e
despeja a lista de widgets Dojo (id | label) para ajustar os seletores.
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

from services.driver_manager import DriverManager
from services.flow_utils import _fazer_login
from services.flow_atendimento import iniciar_atendimento, DESCRICAO_PADRAO

USUARIO        = input("Usuário: ").strip()
SENHA          = input("Senha: ").strip()
NUMERO_CHAMADO = input("Número do chamado (em Atendimento Programado): ").strip()


def log(msg, nivel="info"):
    prefixos = {"info": "[INFO]", "status": "[STATUS]", "success": "[OK]", "error": "[ERRO]"}
    print(f"{prefixos.get(nivel, '[?]')} {msg}")


# JS que le o registry do Dojo e devolve "id | label" de cada widget com label.
_JS_REGISTRY = r"""
var out = [];
try {
    var reg = require("dijit/registry");
    var arr = reg.toArray();
    for (var i = 0; i < arr.length; i++) {
        var w = arr[i], label = "";
        try {
            if (w.label) label = w.label;
            else if (w.get) { try { label = w.get('label'); } catch (e) {} }
            if (!label && w.domNode) label = w.domNode.textContent;
        } catch (e) {}
        label = (label || "").replace(/\s+/g, ' ').trim();
        if (label) out.push((w.id || '?') + ' | ' + label);
    }
} catch (e) {
    return ['ERRO registry: ' + e];
}
return out;
"""


def dump_registry(driver, titulo="MODO CAPTURA — estado atual"):
    """Despeja os widgets Dojo (id | label) da tela ATUAL, sem clicar em nada.
    Usado apos abrir o pop-up para levantar seus campos e o botao de salvar."""
    log("─" * 55, "info")
    log(titulo, "status")
    log("─" * 55, "info")
    try:
        itens = driver.execute_script(_JS_REGISTRY) or []
    except Exception as e:
        log(f"Falha ao ler o registry: {e}", "error")
        return
    com_label = [i for i in itens if i and "| " in i and i.split("| ", 1)[1].strip()]
    log(f"Registry ({len(com_label)} itens com label):", "status")
    for linha in com_label:
        print(f"⚪ {linha}")
    log("─" * 55, "info")


def capturar_menu(driver):
    """
    MODO CAPTURA: reabre o menu Actions (best effort), revela os submenus e
    despeja todos os widgets Dojo (id | label). Nada aqui altera o chamado.
    """
    log("─" * 55, "info")
    log("MODO CAPTURA — despejando widgets do menu Dojo...", "status")
    log("─" * 55, "info")

    # Reabrir o menu Actions (ignora erros — a ideia e so revelar os itens)
    try:
        driver.find_element(By.ID, "menuActions").click()
        time.sleep(1)
    except Exception as e:
        log(f"(nao consegui reabrir 'Actions': {e})", "info")

    # Passar o mouse por cada submenu conhecido para revelar os filhos
    for cabecalho in ["Clock Actions", "Normal Actions", "User Actions", "Supplier Actions"]:
        try:
            el = driver.find_element(
                By.XPATH,
                f"//td[contains(@class,'dijitMenuItemLabel') and "
                f"normalize-space(text())='{cabecalho}']",
            )
            ActionChains(driver).move_to_element(el).perform()
            time.sleep(0.6)
        except Exception:
            pass

    try:
        itens = driver.execute_script(_JS_REGISTRY) or []
    except Exception as e:
        log(f"Falha ao ler o registry: {e}", "error")
        return

    com_label = [i for i in itens if i and "| " in i and i.split("| ", 1)[1].strip()]
    log(f"Registry ({len(com_label)} itens com label):", "status")
    for linha in com_label:
        print(f"⚪ {linha}")
    log("─" * 55, "info")
    log("Copie a lista acima e me mande — vou ajustar os seletores do menu.", "info")


def main():
    dm = DriverManager(log)

    try:
        log("Iniciando Chrome...", "status")
        driver = dm.iniciar_driver_e_navegar()

        if not _fazer_login(driver, USUARIO, SENHA, log):
            log("Login falhou. Encerrando.", "error")
            return

        log("─" * 55, "info")
        log("TESTANDO 'INICIAR ATENDIMENTO' (modo teste, sem salvar)...", "status")
        log("─" * 55, "info")

        ok = iniciar_atendimento(
            driver, log, NUMERO_CHAMADO,
            descricao=DESCRICAO_PADRAO,
            modo_teste=True,
        )

        log("─" * 55, "info")
        if ok:
            log("RESULTADO: chegou ate a descricao. Confira o pop-up no browser.", "success")
            # Chegou no pop-up -> despeja o estado atual para levantar os campos
            # do pop-up e o botao 'Salvar ação' (sem clicar em nada).
            dump_registry(driver, "CAPTURA DO POP-UP — campos e botao de salvar")
        else:
            log("RESULTADO: falhou em algum passo. Veja os logs acima.", "error")
            # Falhou -> reabre o menu Actions e despeja para levantar os seletores.
            capturar_menu(driver)

        log("O chamado NAO sera salvo. Verifique o browser e pressione ENTER para fechar.", "info")
        input("\n>>> Pressione ENTER para encerrar o Chrome <<<\n")

    finally:
        dm.encerrar_driver()


if __name__ == "__main__":
    main()
