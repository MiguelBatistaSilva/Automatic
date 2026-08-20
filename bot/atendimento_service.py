"""
bot/atendimento_service.py — Iniciar Atendimento sem interface.

Mesmo papel do sla_service.py: a orquestracao (login -> laco de chamados) hoje
so existe dentro de state/atendimento_state.py, amarrada a tela do Reflex. Aqui
ela roda sozinha, para o bot poder chamar.

ATENCAO — este fluxo ESCREVE no chamado, diferente do SLA. Com modo_teste=True
o `iniciar_atendimento` vai ate preencher a descricao e PARA antes de clicar em
"Salvar acao": da para exercitar o caminho inteiro, com chamado real, sem
alterar nada. Use isso para testar.
"""
from services.browser_pw import NavegadorPW, _fazer_login_pw
from services.flow_atendimento_pw import DESCRICAO_PADRAO, iniciar_atendimento


def _silencioso(msg, tipo="info"):
    pass


def iniciar_lote(chamados, matricula, senha, log=None, modo_teste=False) -> dict:
    """Inicia o atendimento de varios chamados numa sessao so do navegador.

    Em lote de proposito: abrir um Chrome por chamado seria muito mais lento, e
    e assim que o timer da tela ja funciona hoje.

    Devolve {numero: (ok, detalhe)} contendo SEMPRE todos os chamados da
    entrada — chamado que falhou vem com ok=False e o motivo, nunca ausente.
    """
    log = log or _silencioso
    resultados = {}

    with NavegadorPW(log) as page:
        if not _fazer_login_pw(page, matricula, senha, log):
            return {c: (False, "Falha no login") for c in chamados}

        for numero in chamados:
            log(f"Iniciando atendimento do chamado {numero}...", "status")
            try:
                ok = iniciar_atendimento(
                    page, log, numero, DESCRICAO_PADRAO, modo_teste
                )
                detalhe = "" if ok else "O fluxo nao chegou ao fim"
            except Exception as e:
                # Uma excecao num chamado nao pode derrubar os outros do lote.
                ok, detalhe = False, str(e)
                log(f"Excecao em {numero}: {e}", "error")
            resultados[numero] = (ok, detalhe)

    return resultados
