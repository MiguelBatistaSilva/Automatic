"""
services/flow_resolver_pw.py — Fluxo "Resolvido" (resolver chamado) em Playwright.

    Ações -> Resolvido -> pop-up de ação -> Descrição -> Salvar ação

Criado em 2026-10-01 a partir do que o usuário descreveu: toda ação do Assyst
passa pelo menu Ações e abre o MESMO pop-up de texto (#ManageActionForm_
actionDialog — ver flow_atendimento_pw / flow_programar_pw). O texto é o
MESMO modelo do Aguardando Info do Usuário, com "Testado pelo usuário? (X) Sim"
(`flow_usuario_pw.montar_texto(..., testado=True)`).

REGRA DE NEGÓCIO GARANTIDA AQUI (não só na IA): chamado com SLA ESTOURADO não
pode ser resolvido. Antes de abrir o menu, o fluxo calcula o SLA e recusa.

"Resolvido" fica DIRETO no menu Ações e o fecho é "(X) Sim" — os dois
confirmados pelo usuário em 2026-10-01. Ainda sem teste na tela: validar pelo
modo teste (Simular) antes do primeiro uso.
"""

from services.browser_pw import _navegar_para_chamado_pw, _setor_pw, _usuario_afetado_pw
from services.ckeditor_pw import preencher_formatado_popup
from services.flow_usuario_pw import montar_texto

_SEL_MENU_ACOES = "#menuActions"
_SEL_RESOLVIDO = "td.dijitMenuItemLabel:text-is('Resolvido')"
_SEL_DIALOGO = "#ManageActionForm_actionDialog"
_SEL_SALVAR = "[id='ManageActionForm.btSave']"


def sla_do_chamado(page, log, numero_chamado: str, fila: str) -> dict | None:
    """O cálculo da Análise de SLA para um chamado (None se não deu para ler)."""
    from services.flow_sla_pw import extrair_historico_chamado
    from services.sla_engine import calcular_sla

    historico = extrair_historico_chamado(page, numero_chamado, log)
    if historico is None:
        return None
    return calcular_sla(historico, fila)


def _clicar_resolvido(page, log) -> bool:
    """'Resolvido' fica DIRETO no menu Ações — não em 'Ações de relógio'
    (confirmado pelo usuário em 2026-10-01)."""
    page.click(_SEL_MENU_ACOES, timeout=20000)
    try:
        page.locator(_SEL_RESOLVIDO).first.click(timeout=10000)
        return True
    except Exception as e:
        log(f"Não achei 'Resolvido' no menu Ações: {e}", "error")
        return False


def resolver_chamado(page, log, numero_chamado: str, procedimentos: str,
                     fila: str, modo_teste: bool = False) -> tuple[bool, dict]:
    """
    Resolve um chamado, se o SLA estiver no prazo.

    modo_teste=True  -> preenche a descrição e PARA (não clica em 'Salvar ação').
    modo_teste=False -> clica em 'Salvar ação' e confere que o pop-up fechou.

    Retorna (ok, info) — info={"usuario", "setor", "sla", "estourado"}.
    """
    numero_chamado = numero_chamado.strip()
    info = {"usuario": "", "setor": "", "sla": "", "estourado": False}

    sla = sla_do_chamado(page, log, numero_chamado, fila)
    if sla is None:
        log(f"Não consegui calcular o SLA de {numero_chamado}; não vou resolver.", "error")
        info["erro"] = "parou no SLA: não consegui ler o histórico do chamado"
        return False, info
    info["sla"], info["estourado"] = sla.get("mensagem", ""), bool(sla.get("estourado"))
    if info["estourado"]:
        log(f"{numero_chamado}: SLA {info['sla']} — chamado estourado NÃO pode "
            "ser resolvido.", "error")
        return False, info

    if not _navegar_para_chamado_pw(page, numero_chamado, log):
        log(f"Não foi possível abrir o chamado {numero_chamado}.", "error")
        info["erro"] = "parou ao abrir o chamado"
        return False, info
    info["usuario"], info["setor"] = _usuario_afetado_pw(page), _setor_pw(page)
    if not info["usuario"]:
        log("Não consegui ler o Usuário afetado do chamado.", "error")
        info["erro"] = "parou ao ler o nome do Usuário afetado"
        return False, info

    try:
        if not _clicar_resolvido(page, log):
            info["erro"] = "parou no menu: não achei 'Resolvido' em Ações"
            return False, info
        page.locator(_SEL_DIALOGO).wait_for(state="visible", timeout=15000)
    except Exception as e:
        log(f"O pop-up de 'Resolvido' não abriu: {e}", "error")
        info["erro"] = "parou esperando o pop-up de 'Resolvido' abrir"
        return False, info
    log("Pop-up de 'Resolvido' aberto.", "success")

    if not preencher_formatado_popup(
            page, log, montar_texto(info["usuario"], procedimentos, testado=True)):
        info["erro"] = "parou ao preencher o texto no pop-up"
        return False, info

    if modo_teste:
        log("MODO TESTE: descrição preenchida. Parando ANTES de 'Salvar ação'. "
            "Nada foi alterado no chamado.", "status")
        return True, info

    try:
        page.click(_SEL_SALVAR, timeout=15000)
    except Exception as e:
        log(f"Não consegui clicar em 'Salvar ação': {e}", "error")
        info["erro"] = "parou no botão 'Salvar ação' (não consegui clicar)"
        return False, info
    try:
        page.locator(_SEL_DIALOGO).wait_for(state="hidden", timeout=20000)
    except Exception:
        # O Assyst não aceitou (o pop-up continua aberto). Diz POR QUÊ: lê o
        # aviso que ele mostrou e guarda um print (bug do R2470669, 02/10).
        motivo = _motivo_recusa(page)
        foto = _print_da_tela(page, numero_chamado)
        log(f"O Assyst não salvou o Resolvido: {motivo or 'sem mensagem visível'}"
            + (f" (print: {foto})" if foto else ""), "error")
        info["erro"] = f"o Assyst não salvou — {motivo or 'sem mensagem visível'}"
        return False, info
    log("Chamado resolvido.", "success")
    return True, info


def _motivo_recusa(page) -> str:
    """Textos de aviso/erro visíveis na tela depois do Salvar (validação do
    Assyst/Dojo). Vazio se não achar nada."""
    try:
        textos = page.evaluate("""() => {
            const sel = ['.dijitTooltipContents', '[role=alert]', '.errorMessage',
                         '.axios-error', '.dijitValidationTextBoxError', '.messageBox',
                         '.error', '.validationMessage'];
            const vistos = new Set();
            for (const s of sel) for (const e of document.querySelectorAll(s)) {
                const t = (e.innerText || '').trim();
                if (t && e.offsetParent !== null) vistos.add(t.slice(0, 200));
            }
            return Array.from(vistos);
        }""")
        return " | ".join(textos)
    except Exception:
        return ""


def _print_da_tela(page, numero_chamado: str) -> str:
    try:
        from datetime import datetime
        from services.paths import APP_LOCAL_DIR
        pasta = APP_LOCAL_DIR / "capturas"
        pasta.mkdir(parents=True, exist_ok=True)
        arq = pasta / f"resolver_{numero_chamado}_{datetime.now():%Y%m%d_%H%M%S}.png"
        page.screenshot(path=str(arq))
        return str(arq)
    except Exception:
        return ""
