"""
services/flow_bc.py — Fluxo de adicao de Base de Conhecimento em chamados ja criados.
Recebe uma lista de numeros de chamados filhos e executa apenas a Fase 2 (BC).
A chave do checkpoint e derivada do primeiro filho da lista.
"""
from services.checkpoint import (
    inicializar, marcar_concluido_linha,
    existe_pendente, foi_concluido, status_linha,
    STATUS_PENDENTE, STATUS_CONCLUIDO,
)
from services.flow_utils import (
    _sessao_expirada, _fazer_login,
    _navegar_para_chamado, _adicionar_bc,
)


def _chave_checkpoint(filhos: list[str]) -> str:
    """Gera a chave do checkpoint a partir do primeiro filho da lista."""
    return f"bc_{filhos[0].strip()}"


def execute_bc_flow(driver, filhos: list[str], usuario: str, senha: str,
                    log, kb_function, iniciar_do_zero: bool = False):
    """
    Fluxo BC: recebe lista de numeros de chamados filhos ja criados
    e adiciona a Base de Conhecimento em cada um.
    Checkpoint indexado pelo primeiro filho da lista.
    """
    filhos = [f.strip() for f in filhos if f.strip()]
    if not filhos:
        log("Nenhum chamado informado.", "error")
        return

    total = len(filhos)
    chave = _chave_checkpoint(filhos)

    # -----------------------------------------------------------
    # CHECKPOINT
    # -----------------------------------------------------------
    if iniciar_do_zero or not existe_pendente(chave):
        log("Inicializando checkpoint BC...", "info")
        inicializar(chave, total)
    else:
        concluidos = sum(1 for i in range(total) if status_linha(chave, i) == STATUS_CONCLUIDO)
        pendentes  = total - concluidos
        log(f"Retomando execucao BC: {concluidos} concluidas, {pendentes} pendentes.", "status")

    # -----------------------------------------------------------
    # LOGIN
    # -----------------------------------------------------------
    if not _fazer_login(driver, usuario, senha, log):
        return

    # -----------------------------------------------------------
    # LOOP PRINCIPAL
    # -----------------------------------------------------------
    log(f"--- INICIANDO PROCESSAMENTO BC ({total} chamados) ---", "status")

    for index, numero_filho in enumerate(filhos):

        st = status_linha(chave, index)

        if st == STATUS_CONCLUIDO:
            log(f"Chamado {index + 1}/{total} ({numero_filho}): ja concluido, pulando.", "info")
            continue

        log(f"--- Chamado {index + 1}/{total}: {numero_filho} ---", "status")

        # Verificar sessao
        if _sessao_expirada(driver):
            if not _fazer_login(driver, usuario, senha, log):
                return

        # Navegar para o chamado filho
        if not _navegar_para_chamado(driver, numero_filho, log):
            log(f"Nao foi possivel acessar {numero_filho}. Pulando.", "error")
            continue

        # Verificar sessao antes da BC
        if _sessao_expirada(driver):
            if not _fazer_login(driver, usuario, senha, log):
                return

        # Adicionar BC
        log("Adicionando Base de Conhecimento...", "status")
        bc_ok = _adicionar_bc(driver, log, kb_function)

        if bc_ok:
            marcar_concluido_linha(chave, index)
            log(f"Checkpoint: {numero_filho} marcado como CONCLUIDO.", "success")
        else:
            log(f"BC nao adicionada em {numero_filho}. Sera retentada na proxima execucao.", "error")

        # Verificar sessao apos BC
        if _sessao_expirada(driver):
            if not _fazer_login(driver, usuario, senha, log):
                return

    # -----------------------------------------------------------
    # RESUMO FINAL
    # -----------------------------------------------------------
    concluidos = sum(1 for i in range(total) if status_linha(chave, i) == STATUS_CONCLUIDO)
    pendentes  = total - concluidos

    if pendentes > 0:
        log(f"Execucao BC finalizada: {concluidos}/{total} concluidas. "
            f"{pendentes} pendentes — execute novamente para completar.", "status")
    else:
        log(f"Base de Conhecimento adicionada em todos os {total} chamados!", "success")