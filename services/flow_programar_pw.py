"""
services/flow_programar_pw.py — Fluxo "Atendimento Programado" em Playwright.

    Ações -> Ações de relógio -> Atendimento Programado
    -> pop-up "ATEN PROG ação no evento ..." -> Descrição -> Salvar ação

Irmão do flow_atendimento_pw (mesmo menu, mesmo tipo de pop-up). Criado em
2026-09-30 a partir do teste_programar_atendimento.py, validado pelo usuário.

Só a DESCRIÇÃO é preenchida. Os campos Data/hora do pop-up (HOJE/AGORA) ficam
como estão: o dia e a hora combinados vão só no TEXTO (decisão do usuário).

Texto no padrão da auditoria — azul marinho, com nome/dia/hora/motivo em
vermelho (ver services/ckeditor_pw.py):
    Conforme solicitado pelo(a) Sr.(a) NOME_AFETADO, o atendimento está sendo
    programado para o dia dd/mm às hh:mm.
    Motivo(s): Breve descrição.

Os `except Exception` são largos DE PROPÓSITO, como no flow_atendimento_pw:
um erro num chamado não pode derrubar o lote.
"""

import re

from services.browser_pw import (
    _navegar_para_chamado_pw, _setor_pw, _usuario_afetado_pw,
)
from services.ckeditor_pw import (
    AZUL_MARINHO, VERMELHO, paragrafo, preencher_formatado_popup, trecho,
)

_SEL_MENU_ACOES = "#menuActions"
_SEL_ACOES_RELOGIO = "td.dijitMenuItemLabel:text-is('Ações de relógio')"
_SEL_PROGRAMADO_TXT = "td.dijitMenuItemLabel:text-is('Atendimento Programado')"
_SEL_PROGRAMADO_PARCIAL = "td.dijitMenuItemLabel:has-text('Programado')"
_SEL_DIALOGO = "#ManageActionForm_actionDialog"
_SEL_SALVAR = "[id='ManageActionForm.btSave']"


def normalizar_dia(dia: str) -> str:
    """'2/10', '02/10', '02/10/2026' -> '02/10'. Levanta ValueError se não der."""
    m = re.fullmatch(r"\s*(\d{1,2})/(\d{1,2})(?:/\d{2,4})?\s*", dia or "")
    if not m or not (1 <= int(m[1]) <= 31 and 1 <= int(m[2]) <= 12):
        raise ValueError(f"Dia inválido: '{dia}'. Use dd/mm, ex.: 02/10.")
    return f"{int(m[1]):02d}/{int(m[2]):02d}"


def normalizar_hora(hora: str) -> str:
    """'14:20', '14h20', '14h', '9:05' -> 'hh:mm'. Levanta ValueError se não der."""
    m = re.fullmatch(r"\s*(\d{1,2})\s*[:hH]\s*(\d{2})?\s*", hora or "")
    if not m or int(m[1]) > 23 or (m[2] and int(m[2]) > 59):
        raise ValueError(f"Hora inválida: '{hora}'. Use hh:mm, ex.: 14:20.")
    return f"{int(m[1]):02d}:{m[2] or '00'}"


def montar_texto(nome: str, dia: str, hora: str, motivo: str) -> str:
    a, v = AZUL_MARINHO, VERMELHO
    return (
        paragrafo(trecho("Conforme solicitado pelo(a) Sr.(a) ", a), trecho(nome, v),
                  trecho(", o atendimento está sendo programado para o dia ", a),
                  trecho(dia, v), trecho(" às ", a), trecho(hora, v), trecho(".", a))
        + paragrafo(trecho("Motivo(s): ", a), trecho(motivo, v))
    )


def programar_atendimento(page, log, numero_chamado: str, dia: str, hora: str,
                          motivo: str, modo_teste: bool = False) -> tuple[bool, dict]:
    """
    Registra 'Atendimento Programado' num chamado.

    modo_teste=True  -> preenche a descrição e PARA (não clica em 'Salvar ação').
    modo_teste=False -> clica em 'Salvar ação' e confere que o pop-up fechou.

    Retorna (ok, info) — info={"usuario": ..., "setor": ...} lido do chamado.
    """
    numero_chamado = numero_chamado.strip()
    info = {"usuario": "", "setor": ""}

    if not _navegar_para_chamado_pw(page, numero_chamado, log):
        log(f"Não foi possível abrir o chamado {numero_chamado}.", "error")
        return False, info

    info = {"usuario": _usuario_afetado_pw(page), "setor": _setor_pw(page)}
    if not info["usuario"]:
        # O nome é obrigatório no texto da auditoria: sem ele, não grava.
        log("Não consegui ler o Usuário afetado do chamado.", "error")
        return False, info

    try:
        page.click(_SEL_MENU_ACOES, timeout=20000)
        page.hover(_SEL_ACOES_RELOGIO, timeout=10000)
    except Exception as e:
        log(f"Erro ao abrir Ações -> Ações de relógio: {e}", "error")
        return False, info

    try:
        page.click(_SEL_PROGRAMADO_TXT, timeout=5000)
    except Exception:
        try:
            page.click(_SEL_PROGRAMADO_PARCIAL, timeout=5000)
        except Exception as e:
            log(f"Erro ao clicar em 'Atendimento Programado': {e}", "error")
            log("Confirme que essa ação está disponível no chamado.", "info")
            return False, info
    log("Clicado em 'Atendimento Programado'.", "success")

    try:
        page.locator(_SEL_DIALOGO).wait_for(state="visible", timeout=15000)
    except Exception as e:
        log(f"O pop-up da ação não abriu: {e}", "error")
        return False, info

    texto = montar_texto(info["usuario"], dia, hora, motivo)
    if not preencher_formatado_popup(page, log, texto):
        return False, info

    if modo_teste:
        log("MODO TESTE: descrição preenchida. Parando ANTES de 'Salvar ação'. "
            "Nada foi alterado no chamado.", "status")
        return True, info

    try:
        page.click(_SEL_SALVAR, timeout=15000)
    except Exception as e:
        log(f"Erro ao clicar em 'Salvar ação': {e}", "error")
        return False, info

    # Pop-up fechou = o Assyst aceitou. Sem isso, um erro de validação no
    # diálogo passaria por sucesso.
    try:
        page.locator(_SEL_DIALOGO).wait_for(state="hidden", timeout=20000)
    except Exception:
        log("O pop-up não fechou depois de salvar — confira o chamado.", "error")
        return False, info
    log("Atendimento programado salvo.", "success")
    return True, info
