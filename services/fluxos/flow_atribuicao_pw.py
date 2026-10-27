"""
services/fluxos/flow_atribuicao_pw.py — Fluxo "Atribuição Interna" em Playwright (21/10).

Caminho no Assyst:
    Ações -> Atribuição Interna -> Departamento de Serviço atribuído
    [-> Usuário Atribuído] -> texto -> Salvar ação.

Não mexe no relógio do SLA. O pop-up é o mesmo de toda ação
(#ManageActionForm_actionDialog, título "ASSIGN ação no evento ..."); a fila e
o técnico são type-aheads IGUAIS aos da Requisição (assignedServDept /
assignee), só que no formulário da ação: ids `ManageActionForm_NONE_<campo>_...`
em vez de `ManageEventForm_<PREFIXO>_...` (captura do R2493651, 21/10). A
digitação e a escolha do item reusam as peças do flow_requisicao_pw.

"Puxar para mim": o pop-up já traz o técnico logado e a fila dele em
'Usuário/Departamento de Serviço de acionamento' — é de lá que vêm os valores.

SELETOR DO MENU SÓ POR TEXTO (como Adicionar Informação / Fornecedor): se o
texto do item mudar no Assyst, recapturar.
"""

import unicodedata
from types import SimpleNamespace

from services.assyst.browser_pw import _navegar_para_chamado_pw, _setor_pw, _usuario_afetado_pw
from services.assyst.ckeditor_pw import (AZUL_MARINHO, VERMELHO, paragrafo,
                                  preencher_formatado_popup, texto_livre, trecho)
from services.fluxos.flow_requisicao_pw import (_JS_OPCOES, _clicar_sugestao, _escolher_opcao,
                                         _escrever, _valor_gravado)
from services.regras.sla_engine import FILAS

_SEL_MENU_ACOES = "#menuActions"
_SEL_ATRIBUICAO_TXT = "td.dijitMenuItemLabel:text-is('Atribuição Interna')"
_SEL_DIALOGO = "#ManageActionForm_actionDialog"
_SEL_SALVAR = "[id='ManageActionForm.btSave']"

_FORM = "ManageActionForm_NONE"
FILA = SimpleNamespace(sufixo="assignedServDept", rotulo="Departamento de Serviço atribuído")
TECNICO = SimpleNamespace(sufixo="assignee", rotulo="Usuário Atribuído")
_ACIONAMENTO_TECNICO = f"#{_FORM}_actioningUser_textNode"
_ACIONAMENTO_FILA = f"#{_FORM}_actioningServDept_textNode"

# Textos padrão (21/10). ESCALONAR = o técnico não resolveu e passa adiante;
# PUXAR = o técnico pega o chamado para si (o mais usado); CONTATO = pegou e
# já falou com o usuário.
ESCALONAR, PUXAR, CONTATO, LIVRE = "escalonar", "puxar", "contato", "livre"
MODOS = (ESCALONAR, PUXAR, CONTATO, LIVRE)


def _sem_acento(s: str) -> str:
    t = unicodedata.normalize("NFD", (s or "").strip().lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def nome_da_fila(fila: str) -> str:
    """'fcb' -> '2N CATI FCB'; 'Polo Iguatu' -> '2N CATI Polo Iguatu'. A busca
    do Assyst é pelo COMEÇO do nome, então o '2N CATI' precisa ir junto."""
    f = (fila or "").strip()
    if not f:
        return ""
    for conhecida in FILAS:
        if _sem_acento(conhecida) in (_sem_acento(f), _sem_acento("2N CATI " + f)):
            return conhecida
    return f if _sem_acento(f).startswith("2n ") else "2N CATI " + f


def montar_texto(modo: str, detalhe: str = "") -> str:
    """HTML do texto da ação. `detalhe` = motivo (ESCALONAR, em vermelho; uma
    linha fica na mesma linha do rótulo, várias viram lista) ou o texto livre."""
    a, v = AZUL_MARINHO, VERMELHO
    if modo == ESCALONAR:
        linhas = [l.strip() for l in detalhe.strip().split("\n") if l.strip()]
        if len(linhas) == 1:
            atividades = [paragrafo(trecho("Atividades realizadas: ", a), trecho(linhas[0], v))]
        else:
            atividades = [paragrafo(trecho("Atividades realizadas:", a)),
                          texto_livre(detalhe.strip(), v)]
        return "".join([paragrafo(trecho("Encaminhando para análise.", a)),
                        "<p>&nbsp;</p>", *atividades])
    if modo == PUXAR:
        return "".join([
            paragrafo(trecho("Prezado(a),", a)), "<p>&nbsp;</p>",
            paragrafo(trecho("Informo que sua solicitação encontra-se em análise. "
                             "Em breve entraremos em contato.", a))])
    if modo == CONTATO:
        return paragrafo(trecho("Contato com êxito, suporte realizando intervenção técnica.", a))
    return texto_livre(detalhe.strip())


def _valor(page, sel: str) -> str:
    try:
        return page.locator(sel).first.input_value().strip()
    except Exception:
        return ""


def _escolher(page, log, campo, valor: str) -> bool:
    """Type-ahead do pop-up: digita, espera a lista e clica no item certo (a
    regra conservadora do `_escolher_opcao`: ambíguo = não escolhe)."""
    base = f"{_FORM}_{campo.sufixo}_comboBox"
    sel = f"#{_FORM}_{campo.sufixo}_textNode"
    atual = _valor(page, sel)
    if _sem_acento(atual) == _sem_acento(valor):
        log(f"{campo.rotulo}: {atual} (já estava)", "success")
        return True
    opcoes = None
    for tecla_a_tecla in (False, True):
        try:
            caixa = page.locator(sel).first
            caixa.wait_for(state="visible", timeout=15000)
            _escrever(caixa, valor, tecla_a_tecla)
            page.wait_for_selector(f"#{base}_dropdown", state="visible",
                                   timeout=15000 if tecla_a_tecla else 6000)
        except Exception:
            if not tecla_a_tecla:
                continue
            log(f"'{campo.rotulo}': a lista de sugestões não abriu para {valor!r}.", "error")
            return False
        opcoes = page.evaluate(_JS_OPCOES, f"{base}_popup") or []
        break
    alvo = _escolher_opcao(opcoes or [], valor)
    if alvo is None:
        vistas = " | ".join(o["texto"] for o in (opcoes or [])[:8]) or "nenhuma"
        log(f"'{campo.rotulo}': {valor!r} não identifica UM item. Opções: {vistas}.", "error")
        return False
    if not _clicar_sugestao(page, log, campo, alvo):
        return False
    gravado = _valor_gravado(page, sel)
    if not gravado:
        log(f"'{campo.rotulo}': cliquei em {alvo['texto']!r} mas o campo ficou vazio.", "error")
        return False
    log(f"{campo.rotulo}: {gravado}", "success")
    return True


def atribuir_interna(page, log, numero_chamado: str, conteudo_html: str,
                     fila: str = "", tecnico: str = "", para_mim: bool = False,
                     modo_teste: bool = False) -> tuple[bool, dict]:
    """
    Atribui o chamado a uma fila (e, opcionalmente, a um técnico).

    para_mim=True -> técnico = o logado; fila = `fila` ou, se vazia, a dele.
    modo_teste=True -> preenche tudo e PARA antes de 'Salvar ação'.

    Retorna (ok, info); info = {"usuario", "setor"} do chamado, mais "fila" e
    "tecnico" efetivamente escolhidos.
    """
    numero_chamado = numero_chamado.strip()

    # 1. Navegar até o chamado
    if not _navegar_para_chamado_pw(page, numero_chamado, log):
        log(f"Nao foi possivel abrir o chamado {numero_chamado}.", "error")
        return False, {}
    info = {"usuario": _usuario_afetado_pw(page), "setor": _setor_pw(page)}

    # 2. Ações -> Atribuição Interna
    try:
        page.click(_SEL_MENU_ACOES, timeout=20000)
        page.click(_SEL_ATRIBUICAO_TXT, timeout=10000)
        log("Clicado em 'Atribuição Interna'.", "success")
    except Exception as e:
        log(f"Erro ao abrir 'Ações -> Atribuição Interna': {e}", "error")
        return False, info

    # 3. Esperar o pop-up
    try:
        page.locator(_SEL_DIALOGO).wait_for(state="visible", timeout=15000)
        page.locator(f"#{_FORM}_{FILA.sufixo}_textNode").wait_for(state="visible",
                                                                  timeout=15000)
        log("Pop-up da Atribuição Interna aberto.", "success")
    except Exception as e:
        log(f"O pop-up da ação não abriu: {e}", "error")
        return False, info
    # O campo aparece antes de o type-ahead estar pronto: digitar na hora se
    # perdia e a lista de sugestões nunca abria (22/10, 2125861 com a fila
    # vazia; simulado: sem pausa falha, com 2 s preenche tudo).
    page.wait_for_timeout(2000)

    # 4. Quem e para onde
    if para_mim:
        tecnico = _valor(page, _ACIONAMENTO_TECNICO)
        fila = fila or _valor(page, _ACIONAMENTO_FILA)
        if not tecnico or not fila:
            log("Não consegui ler o técnico logado / a fila dele no pop-up.", "error")
            return False, info
    fila = nome_da_fila(fila)
    if not fila:
        log("Falta a fila (Departamento de Serviço atribuído).", "error")
        return False, info
    info.update(fila=fila, tecnico=tecnico)

    # 5. Fila primeiro: a lista de técnicos pode depender dela
    if not _escolher(page, log, FILA, fila):
        return False, info
    if tecnico and not _escolher(page, log, TECNICO, tecnico):
        return False, info

    # 6. Texto
    if not preencher_formatado_popup(page, log, conteudo_html):
        log("Nao foi possivel preencher o texto da atribuição.", "error")
        return False, info

    # 7. Modo teste: para aqui
    if modo_teste:
        log("MODO TESTE: pop-up preenchido. Parando ANTES de 'Salvar ação'. "
            "Nada foi alterado no chamado.", "status")
        return True, info

    # 8. Salvar e confirmar que o pop-up fechou
    try:
        page.click(_SEL_SALVAR, timeout=15000)
        page.locator(_SEL_DIALOGO).wait_for(state="hidden", timeout=15000)
    except Exception as e:
        log(f"A ação pode NAO ter sido registrada ({e}). Confira o chamado.", "error")
        return False, info
    log(f"Chamado {numero_chamado} atribuído a {fila}"
        + (f" / {tecnico}" if tecnico else "") + ".", "success")
    return True, info
