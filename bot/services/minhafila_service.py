"""
bot/minhafila_service.py — Minha Fila sem interface.

So existe aqui: nao ha tela no app desktop para este fluxo (ver
services/flow_minhafila_pw.py). Mesmo papel do sla_service.py: a orquestracao
(login -> leitura da grade) roda sozinha, para o bot poder chamar.

SO LEITURA: abre a fila do tecnico e le a grade. Nao altera nada.
"""
from services.browser_pw import NavegadorPW, _fazer_login_pw
from services.flow_minhafila_pw import ler_fila


def _silencioso(msg, tipo="info"):
    pass


def consultar_fila(matricula, senha, log=None) -> list[dict] | None:
    """Roda a consulta de ponta a ponta e devolve [{referencia, afetado, secao}, ...].

    None em falha tecnica (login ou grade que nao carregou); o chamador deve
    distinguir isso de fila vazia (lista vazia) para nao reportar as duas
    coisas com a mesma mensagem.
    """
    log = log or _silencioso

    with NavegadorPW(log) as page:
        if not _fazer_login_pw(page, matricula, senha, log):
            return None
        return ler_fila(page, log)
