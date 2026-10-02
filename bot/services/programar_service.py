"""
bot/programar_service.py — Atendimento Programado sem interface.

Mesmo papel do atendimento_service.py: a orquestração (login -> laço de
chamados) roda sozinha, para o Assistente (e, se um dia quiser, o bot) chamar.

ATENÇÃO — este fluxo ESCREVE no chamado. Com modo_teste=True ele preenche a
descrição e PARA antes de 'Salvar ação'.
"""

from services.browser_pw import NavegadorPW, _fazer_login_pw
from services.flow_programar_pw import programar_atendimento


def _silencioso(msg, tipo="info"):
    pass


def programar_lote(chamados, dia, hora, motivo, matricula, senha, log=None,
                   modo_teste=False) -> dict:
    """Programa o MESMO dia/hora/motivo em vários chamados, numa sessão só.

    Devolve {numero: (ok, detalhe, info)} com SEMPRE todos os chamados da
    entrada — o que falhou vem com ok=False e o motivo, nunca ausente.
    """
    log = log or _silencioso
    resultados = {}
    with NavegadorPW(log) as page:
        if not _fazer_login_pw(page, matricula, senha, log):
            return {c: (False, "Falha no login", {}) for c in chamados}
        for numero in chamados:
            log(f"Programando atendimento do chamado {numero}...", "status")
            try:
                ok, info = programar_atendimento(page, log, numero, dia, hora,
                                                 motivo, modo_teste)
                detalhe = "" if ok else "O fluxo não chegou ao fim"
            except Exception as e:
                ok, detalhe, info = False, str(e), {}
                log(f"Exceção em {numero}: {e}", "error")
            resultados[numero] = (ok, detalhe, info)
    return resultados
