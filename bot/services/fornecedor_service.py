"""
bot/fornecedor_service.py — Aguardando Info do Fornecedor sem interface.

So existe aqui: nao ha tela no app desktop para este fluxo (ver
services/flow_fornecedor_pw.py). Mesmo papel do informacao_service.py: a
orquestracao (login -> laco de chamados) roda sozinha, para o bot poder
chamar.

ATENCAO — este fluxo ESCREVE no chamado. Com modo_teste=True o
`aguardar_info_fornecedor` vai ate preencher o texto e PARA antes de clicar
em "Salvar acao": da para exercitar o caminho inteiro, com chamado real, sem
alterar nada. Use isso para testar.
"""
from services.browser_pw import NavegadorPW, _fazer_login_pw
from services.flow_fornecedor_pw import aguardar_info_fornecedor


def _silencioso(msg, tipo="info"):
    pass


def aguardar_lote(chamados, texto, matricula, senha, log=None, modo_teste=False) -> dict:
    """Adiciona o MESMO texto (via 'Aguardando Info do Fornecedor') a varios
    chamados numa sessao so do navegador.

    Devolve {numero: (ok, detalhe)} contendo SEMPRE todos os chamados da
    entrada — chamado que falhou vem com ok=False e o motivo, nunca ausente.
    """
    log = log or _silencioso
    resultados = {}

    with NavegadorPW(log) as page:
        if not _fazer_login_pw(page, matricula, senha, log):
            return {c: (False, "Falha no login") for c in chamados}

        for numero in chamados:
            log(f"Registrando Aguardando Info do Fornecedor no chamado {numero}...", "status")
            try:
                ok = aguardar_info_fornecedor(page, log, numero, texto, modo_teste)
                detalhe = "" if ok else "O fluxo nao chegou ao fim"
            except Exception as e:
                # Uma excecao num chamado nao pode derrubar os outros do lote.
                ok, detalhe = False, str(e)
                log(f"Excecao em {numero}: {e}", "error")
            resultados[numero] = (ok, detalhe)

    return resultados
