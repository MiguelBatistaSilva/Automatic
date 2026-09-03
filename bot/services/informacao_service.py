"""
bot/informacao_service.py — Adicionar Informação sem interface.

So existe aqui: nao ha tela no app desktop para este fluxo (ver
services/flow_informacao_pw.py). Mesmo papel do atendimento_service.py: a
orquestracao (login -> laco de chamados) roda sozinha, para o bot poder
chamar.

ATENCAO — este fluxo ESCREVE no chamado. Com modo_teste=True o
`adicionar_informacao` vai ate preencher o texto e PARA antes de clicar em
"Salvar acao": da para exercitar o caminho inteiro, com chamado real, sem
alterar nada. Use isso para testar.
"""
from services.browser_pw import NavegadorPW, _fazer_login_pw
from services.flow_informacao_pw import adicionar_informacao


def _silencioso(msg, tipo="info"):
    pass


def adicionar_lote(chamados, texto, matricula, senha, log=None, modo_teste=False) -> dict:
    """Adiciona o MESMO texto a varios chamados numa sessao so do navegador.

    Em lote de proposito, mesmo motivo do atendimento_service: abrir um
    Chrome por chamado seria muito mais lento.

    Devolve {numero: (ok, detalhe)} contendo SEMPRE todos os chamados da
    entrada — chamado que falhou vem com ok=False e o motivo, nunca ausente.
    """
    log = log or _silencioso
    resultados = {}

    with NavegadorPW(log) as page:
        if not _fazer_login_pw(page, matricula, senha, log):
            return {c: (False, "Falha no login") for c in chamados}

        for numero in chamados:
            log(f"Adicionando informação no chamado {numero}...", "status")
            try:
                ok = adicionar_informacao(page, log, numero, texto, modo_teste)
                detalhe = "" if ok else "O fluxo nao chegou ao fim"
            except Exception as e:
                # Uma excecao num chamado nao pode derrubar os outros do lote.
                ok, detalhe = False, str(e)
                log(f"Excecao em {numero}: {e}", "error")
            resultados[numero] = (ok, detalhe)

    return resultados
