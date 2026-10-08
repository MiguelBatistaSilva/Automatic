"""
services/flow_info_recebida_pw.py — As ações de RETOMADA do relógio (2026-10-06).

As ações de relógio do Assyst vêm em PARES (regra do usuário): o chamado
pausado com uma ação tem que ser retomado com o par DELA.

    Pausa                           -> Retomada (este arquivo)
    Aguardando Info do Usuário *    -> Info Recebidas do Usuário *
    Aguardando Info do Fornecedor   -> Info Recebida do Fornecedor
    (Programar Atendimento          -> Iniciar Atendimento: flow_atendimento_pw)

Caminho no Assyst (o mesmo dos fluxos de pausa):
    Ações -> Ações de relógio -> <ação> -> texto -> Salvar ação.

Os dois rótulos foram confirmados pelo usuário exatamente assim — plural e
asterisco no do Usuário, singular sem asterisco no do Fornecedor. O seletor
compara o texto EXATO (text-is), como nos fluxos de pausa.

Arquivo NOVO de propósito: os fluxos de pausa (flow_usuario_pw,
flow_fornecedor_pw) não foram tocados. O caminho comum fica em
`_executar_acao` uma vez só, para as duas retomadas.

Texto (padrão da auditoria):
  - Usuário: script fixo, azul marinho, com o NOME em vermelho — lido do
    chamado; sem nome, não grava (mesma regra do Aguardando Usuário).
  - Fornecedor: texto livre do técnico, em azul marinho.
"""

from services.browser_pw import _navegar_para_chamado_pw, _setor_pw, _usuario_afetado_pw
from services.ckeditor_pw import (
    AZUL_MARINHO, VERMELHO, paragrafo, preencher_formatado_popup, texto_livre, trecho,
)

ROTULO_USUARIO = "Info Recebidas do Usuário *"
ROTULO_FORNECEDOR = "Info Recebida do Fornecedor"

_SEL_MENU_ACOES = "#menuActions"
_SEL_ACOES_RELOGIO = "td.dijitMenuItemLabel:text-is('Ações de relógio')"
_SEL_DIALOGO = "#ManageActionForm_actionDialog"
_SEL_SALVAR = "[id='ManageActionForm.btSave']"


def _sel_item(rotulo: str) -> str:
    return f"td.dijitMenuItemLabel:text-is('{rotulo}')"


def montar_texto_usuario(nome: str) -> str:
    """Script fixo da auditoria (usuário, 06/10). A concordância ("informações
    recebida") é a do modelo da auditoria — não corrigir."""
    a, v = AZUL_MARINHO, VERMELHO
    return paragrafo(
        trecho("Pendência sanada após informações recebida do(a) senhor(a) ", a),
        trecho(nome, v),
        trecho(", atendimento retomado.", a),
    )


def _executar_acao(page, log, numero_chamado: str, rotulo: str, montar_html,
                   modo_teste: bool) -> tuple[bool, dict]:
    """Caminho comum: chamado -> Ações -> Ações de relógio -> `rotulo` ->
    pop-up -> texto -> Salvar ação.

    `montar_html(info) -> str | None` monta o texto com o que foi lido do
    chamado; None = não dá para gravar (o motivo já foi logado).

    Retorna (ok, info) no mesmo contrato dos fluxos de pausa: info =
    {"usuario", "setor"}, vazio só se nem o chamado abriu.
    """
    numero_chamado = numero_chamado.strip()

    # 1. Navegar ate o chamado
    if not _navegar_para_chamado_pw(page, numero_chamado, log):
        log(f"Nao foi possivel abrir o chamado {numero_chamado}.", "error")
        return False, {}

    info = {"usuario": _usuario_afetado_pw(page), "setor": _setor_pw(page)}

    # 2. Texto montado ANTES de abrir o menu: se faltar o nome, nem abre o pop-up.
    html = montar_html(info)
    if html is None:
        return False, info

    # 3. Menu 'Ações'
    try:
        page.click(_SEL_MENU_ACOES, timeout=20000)
        log("Menu 'Ações' aberto.", "success")
    except Exception as e:
        log(f"Erro ao abrir o menu 'Ações': {e}", "error")
        return False, info

    # 4. Submenu 'Ações de relógio' (passa o mouse por cima)
    try:
        page.hover(_SEL_ACOES_RELOGIO, timeout=10000)
        log("Submenu 'Ações de relógio' revelado.", "success")
    except Exception as e:
        log(f"Erro ao revelar 'Ações de relógio': {e}", "error")
        return False, info

    # 5. A ação de retomada
    try:
        page.click(_sel_item(rotulo), timeout=10000)
        log(f"Clicado em '{rotulo}'.", "success")
    except Exception as e:
        log(f"Erro ao clicar em '{rotulo}': {e}", "error")
        log("Confirme que essa ação está disponível no chamado (ele precisa "
            "estar PAUSADO com a ação correspondente) e que o texto no Assyst "
            f"é exatamente '{rotulo}'.", "info")
        return False, info

    # 6. Pop-up da ação
    try:
        page.locator(_SEL_DIALOGO).wait_for(state="visible", timeout=15000)
        log("Pop-up da ação aberto.", "success")
    except Exception as e:
        log(f"O pop-up da ação não abriu: {e}", "error")
        return False, info

    # 7. Texto colorido pela API do CKEditor (insertHtml — ver ckeditor_pw)
    if not preencher_formatado_popup(page, log, html):
        log("Nao foi possivel preencher o texto da ação.", "error")
        return False, info

    # 8. Modo teste: para aqui, sem salvar
    if modo_teste:
        log("MODO TESTE: texto preenchido. Parando ANTES de 'Salvar ação'. "
            "Nada foi alterado no chamado.", "status")
        return True, info

    # 9. Salvar ação
    try:
        page.click(_SEL_SALVAR, timeout=15000)
        log("Acao salva ('Salvar ação').", "success")
    except Exception as e:
        log(f"Erro ao clicar em 'Salvar ação': {e}", "error")
        return False, info

    # 10. Pop-up fechou = o Assyst aceitou a ação.
    try:
        page.locator(_SEL_DIALOGO).wait_for(state="hidden", timeout=15000)
    except Exception:
        log("O pop-up não fechou apos salvar — a ação pode NAO ter sido "
            "registrada. Confira o chamado manualmente.", "error")
        return False, info

    log(f"'{rotulo}' registrado com sucesso no chamado {numero_chamado}.", "success")
    return True, info


def info_recebida_usuario(page, log, numero_chamado: str,
                          modo_teste: bool = False, nome: str = "") -> tuple[bool, dict]:
    """Retoma o chamado pausado com 'Aguardando Info do Usuário *'. Sem texto
    do técnico: o script é fixo, só entra um nome.

    `nome`: quem passou a informação, quando NÃO é o usuário afetado (~5% dos
    casos, usuário em 08/10 — ex.: "colocando o nome de Clara Navarro").
    Vazio = o usuário afetado lido do chamado, como sempre foi."""
    def montar(info):
        quem = (nome or "").strip() or info["usuario"]
        if not quem:
            log("Nao consegui ler o Usuario afetado do chamado — o script "
                "precisa do nome. Nada foi gravado.", "error")
            return None
        return montar_texto_usuario(quem)
    return _executar_acao(page, log, numero_chamado, ROTULO_USUARIO, montar, modo_teste)


def info_recebida_fornecedor(page, log, numero_chamado: str, informacao: str,
                             modo_teste: bool = False) -> tuple[bool, dict]:
    """Retoma o chamado pausado com 'Aguardando Info do Fornecedor'. Texto
    livre do técnico, em azul marinho (cada linha vira um parágrafo)."""
    def montar(info):
        if not informacao.strip():
            log("Falta o texto da informação recebida do fornecedor.", "error")
            return None
        return texto_livre(informacao)
    return _executar_acao(page, log, numero_chamado, ROTULO_FORNECEDOR, montar, modo_teste)
