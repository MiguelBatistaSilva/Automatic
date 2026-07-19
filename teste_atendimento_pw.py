"""
Script de teste: inicia o atendimento de um chamado usando o PLAYWRIGHT,
sem passar pela interface.

Uso:
    python teste_atendimento_pw.py

Pergunta se deve rodar em MODO TESTE:
  - modo teste (padrao) -> vai ate preencher a descricao e PARA antes de
    'Salvar ação'. Nada e alterado no chamado. O navegador fica aberto ate voce
    apertar ENTER, para voce conferir o pop-up na tela.
  - modo real           -> clica em 'Salvar ação' e ALTERA o chamado de verdade.

Se os seletores do menu Dojo falharem, use o teste_atendimento.py (Selenium),
que tem o MODO CAPTURA para despejar os ids do registry.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.browser_pw import NavegadorPW, _fazer_login_pw
from services.flow_atendimento_pw import iniciar_atendimento, DESCRICAO_PADRAO

USUARIO        = input("Usuário: ").strip()
SENHA          = input("Senha: ").strip()
NUMERO_CHAMADO = input("Número do chamado (em Atendimento Programado): ").strip()

resposta = input("Modo TESTE (nao salva)? [S/n]: ").strip().lower()
MODO_TESTE = resposta != "n"

if not MODO_TESTE:
    confirma = input(
        f"\n!! MODO REAL: o chamado {NUMERO_CHAMADO} SERA alterado no Assyst.\n"
        f"   Digite 'CONFIRMO' para prosseguir: "
    ).strip()
    if confirma != "CONFIRMO":
        print("Cancelado.")
        sys.exit(0)


def log(msg, nivel="info"):
    prefixos = {"info": "[INFO]", "status": "[STATUS]", "success": "[OK]", "error": "[ERRO]"}
    print(f"{prefixos.get(nivel, '[?]')} {msg}")


print(f"\n>>> Descricao a inserir: {DESCRICAO_PADRAO!r}")
print(f">>> Modo: {'TESTE (nao salva)' if MODO_TESTE else 'REAL (salva)'}\n")

ok = False
with NavegadorPW(log) as page:
    if _fazer_login_pw(page, USUARIO, SENHA, log):
        ok = iniciar_atendimento(page, log, NUMERO_CHAMADO,
                                 DESCRICAO_PADRAO, MODO_TESTE)

    if MODO_TESTE:
        input("\n>>> Confira o pop-up na tela. ENTER para fechar o navegador...")

print(f"\n=== RESULTADO: {'OK' if ok else 'FALHOU'} ===")
sys.exit(0 if ok else 1)
