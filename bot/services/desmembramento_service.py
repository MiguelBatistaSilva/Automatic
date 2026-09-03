"""
bot/desmembramento_service.py — Desmembramento sem interface.

Por ora so o modo "So Base" (FluxoBCPW): aplica uma Base de Conhecimento em
chamados filhos que JA EXISTEM. E o unico dos tres modos que nao cria chamado
nenhum — por isso e o primeiro a ser exposto no bot.

Os modos Completo e So Criar entram depois, aqui mesmo, quando houver um jeito
seguro de testa-los (hoje testa-los significa criar chamados de verdade).

Mesmo papel dos outros *_service.py: a orquestracao existe hoje dentro de
state/desmembramento_state.py, amarrada a tela. Aqui ela roda sozinha.
"""
import csv
import io

from services import checkpoint, kb_store
from services.assyst_common import _path_filhos
from services.browser_pw import NavegadorPW
from services.flow_desmembramento_pw import (
    FluxoBCPW,
    FluxoCompletoPW,
    FluxoCriarPW,
    _chave_checkpoint,
)
from services.kb_manager_pw import executar_kb_unica_pw

# Estados possiveis do checkpoint antes de comecar. Quem chama usa isto para
# decidir o que perguntar ao usuario.
NOVO = "novo"
PENDENTE = "pendente"
CONCLUIDO = "concluido"
CORROMPIDO = "corrompido"


def _silencioso(msg, tipo="info"):
    pass


def kbs_disponiveis() -> list:
    """Nomes das Bases de Conhecimento cadastradas, na ordem do kb_store."""
    return [e["nome_artigo"] for e in kb_store.carregar()]


def chave_bc(filhos) -> str:
    """A chave do checkpoint para esta lista (indexada pelo primeiro filho)."""
    return _chave_checkpoint(filhos)


def situacao(chave) -> dict:
    """O que ja existe de checkpoint para esta chave, antes de rodar.

    Existe porque a decisao "retomar ou comecar do zero" e do usuario, e precisa
    ser tomada ANTES de abrir o navegador.
    """
    if checkpoint.esta_corrompido(chave):
        # Nao confundir com "nao existe": arquivo ilegivel tratado como novo
        # faria o fluxo reprocessar tudo achando que e a primeira vez.
        return {"estado": CORROMPIDO, "resumo": ""}
    if checkpoint.foi_concluido(chave):
        return {"estado": CONCLUIDO, "resumo": checkpoint.resumo(chave)}
    if checkpoint.existe_pendente(chave):
        return {"estado": PENDENTE, "resumo": checkpoint.resumo(chave)}
    return {"estado": NOVO, "resumo": ""}


def progresso(chave, total) -> tuple:
    """(concluidos, total) lidos do checkpoint — serve para mostrar andamento.

    O FluxoBCPW nao devolve nada enquanto roda; o checkpoint e a unica fonte de
    verdade sobre o que ja passou, e ele esta em disco. Entao quem quiser
    acompanhar o andamento le daqui, de fora, sem depender do laco do fluxo.
    """
    linhas = checkpoint.status_linhas(chave)
    if not linhas:
        return 0, total
    feitos = sum(1 for l in linhas if l["status"] == checkpoint.STATUS_CONCLUIDO)
    return feitos, len(linhas)


def parse_csv(texto) -> tuple:
    """(colunas, linhas) a partir do CSV colado. Primeira linha e o cabecalho.

    Mesma logica do `_parse_csv` do state, repetida aqui porque aquele modulo
    importa reflex e o service nao pode depender da UI para rodar.
    """
    linhas_csv = list(csv.reader(io.StringIO(texto.strip())))
    if not linhas_csv:
        return [], []
    colunas = [c.strip() for c in linhas_csv[0]]
    linhas = [
        [v.strip() for v in linha]
        for linha in linhas_csv[1:]
        if any(v.strip() for v in linha)
    ]
    return colunas, linhas


def caminho_filhos(chamado_pai):
    """O TXT com os numeros dos filhos criados, gravado pelo proprio fluxo.

    Na tela ele e aberto no Bloco de Notas da maquina do operador. Rodando pelo
    bot isso abriria numa tela que ninguem esta olhando, entao quem chama pega o
    caminho daqui e manda o arquivo pelo chat.
    """
    return _path_filhos(chamado_pai)


def criar_filhos(chamado_pai, csv_texto, descricao, matricula, senha,
                 kb_nome=None, log=None, iniciar_do_zero=False) -> dict:
    """Cria os chamados filhos a partir do CSV.

    kb_nome=None  -> modo "So Criar"      (FluxoCriarPW)
    kb_nome dado  -> modo "Criar + Base"  (FluxoCompletoPW)

    ATENCAO: este fluxo CRIA CHAMADO no Assyst e nao tem modo de teste. Cada
    linha do CSV vira um chamado de verdade.
    """
    log = log or _silencioso
    chamado_pai = chamado_pai.strip()

    colunas, linhas = parse_csv(csv_texto)
    if not linhas:
        return {"ok": False, "erro": "CSV sem linhas (precisa de cabecalho + dados)"}

    kb_function = None
    if kb_nome:
        entrada = next(
            (e for e in kb_store.carregar() if e["nome_artigo"] == kb_nome), None
        )
        if not entrada:
            return {"ok": False, "erro": f"Base de Conhecimento nao encontrada: {kb_nome}"}
        kb_config = {"keyword": entrada["keyword"], "nome_artigo": entrada["nome_artigo"]}

        # voltar_ao_evento=True aqui (ao contrario do So Base): a duplicacao da
        # linha seguinte parte da tela do evento, entao ela precisa voltar.
        def kb_function(page, log_fn):
            return executar_kb_unica_pw(page, log_fn, kb_config, voltar_ao_evento=True)

    # pandas so aqui dentro: importar no topo custaria segundos na subida do bot
    # para um fluxo que talvez nem seja usado.
    import pandas as pd
    df = pd.DataFrame(linhas, columns=colunas)

    with NavegadorPW(log) as page:
        if kb_nome:
            FluxoCompletoPW(page, matricula, senha, log).executar(
                df=df, descricao_base=descricao, numero_chamado=chamado_pai,
                kb_function=kb_function, iniciar_do_zero=iniciar_do_zero,
            )
        else:
            FluxoCriarPW(page, matricula, senha, log).executar(
                df=df, descricao_base=descricao, numero_chamado=chamado_pai,
                iniciar_do_zero=iniciar_do_zero,
            )

    # O fluxo nao retorna nada — o relato sai do checkpoint, que guarda tambem o
    # numero do filho criado em cada linha.
    estados = {l["index"]: l["status"] for l in checkpoint.status_linhas(chamado_pai)}
    detalhe = [
        {
            "linha": i + 1,
            "status": estados.get(i, checkpoint.STATUS_PENDENTE),
            "filho": checkpoint.numero_filho(chamado_pai, i),
        }
        for i in range(len(linhas))
    ]
    criados = sum(1 for d in detalhe if d["filho"])
    concluidos = sum(1 for d in detalhe if d["status"] == checkpoint.STATUS_CONCLUIDO)

    return {
        "ok": True,
        "chave": chamado_pai,
        "kb": kb_nome,
        "total": len(linhas),
        "criados": criados,
        "concluidos": concluidos,
        "resumo": checkpoint.resumo(chamado_pai),
        "detalhe": detalhe,
    }


def aplicar_base(filhos, kb_nome, matricula, senha,
                 log=None, iniciar_do_zero=False) -> dict:
    """Aplica a Base de Conhecimento em cada chamado filho da lista.

    NAO cria chamado: os filhos precisam existir. Devolve um resumo montado a
    partir do checkpoint, que e quem sabe o que de fato passou.
    """
    log = log or _silencioso
    filhos = [f.strip() for f in filhos if f.strip()]
    if not filhos:
        return {"ok": False, "erro": "Nenhum chamado informado"}

    entrada = next(
        (e for e in kb_store.carregar() if e["nome_artigo"] == kb_nome), None
    )
    if not entrada:
        return {"ok": False, "erro": f"Base de Conhecimento nao encontrada: {kb_nome}"}

    kb_config = {"keyword": entrada["keyword"], "nome_artigo": entrada["nome_artigo"]}

    # voltar_ao_evento=False: no modo So Base o passo seguinte e navegar para
    # OUTRO chamado, entao voltar a tela do evento seria trabalho jogado fora.
    def kb_function(page, log_fn):
        return executar_kb_unica_pw(page, log_fn, kb_config, voltar_ao_evento=False)

    chave = _chave_checkpoint(filhos)

    with NavegadorPW(log) as page:
        FluxoBCPW(page, matricula, senha, log).executar(
            filhos=filhos, kb_function=kb_function, iniciar_do_zero=iniciar_do_zero
        )

    # O fluxo nao retorna nada — o relato sai do checkpoint.
    linhas = checkpoint.status_linhas(chave)
    por_indice = {l["index"]: l["status"] for l in linhas}
    detalhe = [
        {"chamado": f, "status": por_indice.get(i, checkpoint.STATUS_PENDENTE)}
        for i, f in enumerate(filhos)
    ]
    feitos = sum(1 for d in detalhe if d["status"] == checkpoint.STATUS_CONCLUIDO)

    return {
        "ok": True,
        "chave": chave,
        "kb": kb_nome,
        "total": len(filhos),
        "concluidos": feitos,
        "resumo": checkpoint.resumo(chave),
        "detalhe": detalhe,
    }
