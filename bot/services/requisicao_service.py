"""
bot/requisicao_service.py — Requisicao de Servico sem interface.

Cria chamados DO ZERO a partir de um bloco colado: uma requisicao por linha,
campos separados por `;` na ordem de ORDEM_COLUNAS.

Duas coisas herdadas do fluxo e que valem manter em qualquer interface:

1. A entrada e validada ANTES de abrir o navegador, e o erro cita o NUMERO DA
   LINHA. Descobrir um campo errado no meio do lote, com metade dos chamados ja
   criados, seria bem pior — aqui nao ha como desfazer.

2. NAO existe checkpoint neste fluxo (diferente do Desmembramento). Se quebrar
   na linha 5 de 10, nao ha retomada: quem for repetir precisa colar so o que
   faltou. Por isso o relatorio diz linha a linha o que entrou.
"""
from services.browser_pw import NavegadorPW, _fazer_login_pw
from services.flow_requisicao_pw import criar_requisicao, parse_entrada
from services.requisicao_campos import ORDEM_COLUNAS, POR_CHAVE, SEPARADOR


def _silencioso(msg, tipo="info"):
    pass


def ordem_dos_campos() -> str:
    """Os rotulos na ordem esperada, derivados do catalogo.

    Derivado, nunca escrito a mao: se a ordem mudar em requisicao_campos.py, a
    ajuda acompanha sozinha em vez de mentir.
    """
    return f"{SEPARADOR} ".join(POR_CHAVE[c].rotulo for c in ORDEM_COLUNAS)


def validar(texto) -> tuple:
    """(requisicoes, erro). Roda antes de qualquer navegador.

    `erro` vem preenchido com a mensagem do parse — que ja cita a linha.
    """
    try:
        requisicoes = parse_entrada(texto)
    except ValueError as e:
        return None, str(e)
    if not requisicoes:
        return None, "Nenhuma linha para processar."
    return requisicoes, None


def criar_lote(requisicoes, matricula, senha, log=None, modo_teste=False) -> list:
    """Cria uma requisicao por item. Devolve um dict por linha, na ordem.

    modo_teste=True preenche tudo e PARA antes de salvar — nada e criado, e o
    numero volta vazio.
    """
    log = log or _silencioso
    total = len(requisicoes)
    resultados = []

    with NavegadorPW(log) as page:
        if not _fazer_login_pw(page, matricula, senha, log):
            return [
                {"linha": i, "ok": False, "numero": "", "usuario": "--",
                 "erro": "Falha no login"}
                for i in range(1, total + 1)
            ]

        for i, valores in enumerate(requisicoes, 1):
            # O que o operador COLOU (a matricula): serve de reserva, porque o
            # NOME so existe depois que o type-ahead resolve na tela.
            colado = valores.get("usuario_afetado", "--")
            log(f"[{i}/{total}] Requisicao para {colado}...", "status")

            try:
                criada = criar_requisicao(page, log, valores, modo_teste)
            except Exception as e:
                log(f"Excecao na linha {i}: {e}", "error")
                resultados.append({"linha": i, "ok": False, "numero": "",
                                   "usuario": colado, "erro": str(e)})
                continue

            if criada is None:
                resultados.append({"linha": i, "ok": False, "numero": "",
                                   "usuario": colado, "erro": "O fluxo nao concluiu"})
            else:
                resultados.append({"linha": i, "ok": True, "numero": criada.numero,
                                   "usuario": criada.usuario, "erro": ""})

    return resultados
