"""
Script de teste: extrai o historico de acoes de um chamado usando o PLAYWRIGHT
(piloto da migracao), sem passar pela interface.

Uso:
    python teste_sla_pw.py

O script vai:
  1. Abrir o Chrome instalado via Playwright (sem chromedriver)
  2. Fazer login
  3. Navegar para o chamado informado
  4. Abrir o Historico de Acoes e extrair as linhas da grade
  5. Imprimir o que extraiu (nao altera NADA no chamado — fluxo so de leitura)

Ao final, oferece rodar o MESMO chamado pelo fluxo Selenium antigo e comparar
as duas extracoes campo a campo. Essa e a validacao que importa na migracao:
o motor novo precisa devolver exatamente o mesmo historico que o antigo.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.browser_pw import NavegadorPW, _fazer_login_pw
from services.flow_sla_pw import extrair_historico_chamado as extrair_pw

USUARIO        = input("Usuário: ").strip()
SENHA          = input("Senha: ").strip()
NUMERO_CHAMADO = input("Número do chamado: ").strip()


def log(msg, nivel="info"):
    prefixos = {"info": "[INFO]", "status": "[STATUS]", "success": "[OK]", "error": "[ERRO]"}
    print(f"{prefixos.get(nivel, '[?]')} {msg}")


def imprimir(historico, rotulo):
    print(f"\n--- {rotulo}: {len(historico)} acoes ---")
    for i, acao in enumerate(historico, 1):
        print(f"[{i}] {acao['data']} | {acao['tipo']} | {acao['autor']} ({acao['depto_autor']})")
        print(f"     atribuido a: {acao['atribuido_a']} ({acao['depto_atribuido']})")
        descricao = acao["descricao"].replace("\n", " ")
        print(f"     descricao: {descricao[:100]}")


def comparar(hist_pw, hist_sel):
    """Compara as duas extracoes campo a campo e relata a primeira divergencia."""
    if len(hist_pw) != len(hist_sel):
        print(f"\n[DIVERGENCIA] quantidade de acoes: Playwright={len(hist_pw)} Selenium={len(hist_sel)}")
        return False

    divergencias = 0
    for i, (a, b) in enumerate(zip(hist_pw, hist_sel), 1):
        for campo in a:
            if a[campo] != b.get(campo):
                divergencias += 1
                print(f"\n[DIVERGENCIA] acao {i}, campo '{campo}':")
                print(f"    Playwright: {a[campo]!r}")
                print(f"    Selenium:   {b.get(campo)!r}")

    if divergencias:
        print(f"\n=== {divergencias} divergencia(s) encontrada(s) ===")
        return False

    print(f"\n=== IDENTICO: {len(hist_pw)} acoes, todos os campos batem ===")
    return True


# --- 1) Extracao via Playwright -------------------------------------------
historico_pw = None
with NavegadorPW(log) as page:
    if _fazer_login_pw(page, USUARIO, SENHA, log):
        historico_pw = extrair_pw(page, NUMERO_CHAMADO, log)

if historico_pw is None:
    log("Playwright nao conseguiu extrair o historico.", "error")
    sys.exit(1)

imprimir(historico_pw, "PLAYWRIGHT")

# --- 2) Comparacao opcional com o fluxo Selenium antigo --------------------
resposta = input("\nRodar o mesmo chamado no Selenium e comparar? [s/N]: ").strip().lower()
if resposta != "s":
    log("Comparacao pulada.", "info")
    sys.exit(0)

from services.driver_manager import DriverManager
from services.flow_utils import _fazer_login
from services.flow_sla import extrair_historico_chamado as extrair_sel

gerente = DriverManager(log)
historico_sel = None
try:
    driver = gerente.iniciar_driver_e_navegar()
    if _fazer_login(driver, USUARIO, SENHA, log):
        historico_sel = extrair_sel(driver, NUMERO_CHAMADO, log)
finally:
    gerente.encerrar_driver()

if historico_sel is None:
    log("Selenium nao conseguiu extrair o historico — sem comparacao.", "error")
    sys.exit(1)

imprimir(historico_sel, "SELENIUM")
sys.exit(0 if comparar(historico_pw, historico_sel) else 1)
