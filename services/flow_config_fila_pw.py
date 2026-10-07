"""
services/flow_config_fila_pw.py — Configurar fila (consulta salva do monitor) no Assyst.

NÃO mexe em chamado: cria, para cada fila, a consulta que lista os chamados
atribuídos àquele Departamento de Serviço e a deixa no menu (2026-10-06).

Caminho (passos do usuário, seletores do HTML que ele mandou):
  1. Monitor de eventos -> botão 'Consulta' (`.monitorQueryButtonIcon`);
  2. Marcar Incidentes, Problemas, Mudanças, Requisições de Serviço;
  3. Marcar Stand Alone, Pacotes, Componentes (já vêm marcados);
  4. Aba 'Atribuição' -> 'Departamento de Serviço atribuído' = a fila;
  5. Marcar 'Somente Departamento de Serviço atribuído' -> Salvar (`#btSave`,
     que só ABRE o pop-up — não grava nada);
  6. Pop-up: Código = Nome = a fila;
  7. Perfil de coluna (select nativo);
  8. Marcar Usuário, Usuário de Contato, Mostrar no menu -> Salvar do pop-up.

As outras caixas (Tarefas, Obsoleto etc.) ficam como estão — decisão do usuário.

Antes das filas, opcionalmente, `criar_perfil` monta um Perfil de coluna NOVO
(colunas na ordem pedida) na mesma página — ver o fim do arquivo (07/10).

Todos os campos são mirados pelo `name`: o id leva prefixo (`NONE_`,
`EventSearchForm_NONE_`) e prefixo já mudou de tela para tela no Assyst.

Simulação (feedback_nao_tocar_assyst): vai até o pop-up preenchido e CANCELA;
o único clique que grava é o Salvar do pop-up.

A lista de sugestões do Departamento NÃO foi capturada nesta tela: assume o
mesmo formato da Requisição (`<campo>_comboBox_dropdown` / `_popupN`) — o
widget é o mesmo. Se falhar no primeiro Simular, é aqui que se ajusta.
"""

import time

from services.browser_pw import _aguardar_pagina_assentar
from services.flow_requisicao_pw import _JS_OPCOES, _escolher_opcao, _norm

_URL_MONITOR = (
    "https://cati.tjce.jus.br/assystweb/application.do#eventsearch%2F"
    "EventSearchDelegatingDispatchAction.do%3Fdispatch%3DmonitorInitNoResults"
)

_SEL_CONSULTA = ".monitorQueryButtonIcon"
_SEL_ABA_ATRIBUICAO = "#filterCriteria_tablist_assignmentTab"
_SEL_DEPARTAMENTO = "input[name='event.lookup.assignedServDept.text']"
_SEL_SALVAR_CONSULTA = "#btSave"
_SEL_CODIGO = "input[name='queryProfileForm.shortCode']"
_SEL_NOME = "input[name='queryProfileForm.name']"
_SEL_PERFIL = "select[name='queryProfileForm.columnProfileId']"
_SEL_SALVAR_POPUP = "[id='queryProfileForm._okButton']"
_SEL_CANCELAR_POPUP = "[id='queryProfileForm._cancelbutton']"

# (name do checkbox, rótulo para o log)
_TIPOS = [
    ("event.lookup.showIncidents.value", "Incidentes"),
    ("event.lookup.showProblems.value", "Problemas"),
    ("event.lookup.showChanges.value", "Mudanças"),
    ("event.lookup.showServiceRequest.value", "Requisições de Serviço"),
    ("event.lookup.showStandAlone.value", "Stand Alone"),
    ("event.lookup.showBundles.value", "Pacotes"),
    ("event.lookup.showComponents.value", "Componentes"),
]
_SO_DEPARTAMENTO = ("event.lookup.servDeptAssignedOnly.value",
                    "Somente Departamento de Serviço atribuído")
_OPCOES_POPUP = [
    ("queryProfileForm.userTypeAssystUser.value", "Usuário"),
    ("queryProfileForm.userTypeContactUser.value", "Usuário de Contato"),
    ("queryProfileForm.showOnMenu.value", "Mostrar no menu"),
]


def _visivel(page, sel: str):
    return page.locator(f"{sel}:visible").first


# ------------------------------------------------------------------ peças

def _marcar(page, log, name: str, rotulo: str) -> bool:
    """Garante a caixa MARCADA. Checkbox do Dojo: o estado está no
    `aria-checked`; clicar numa já marcada a desmarcaria."""
    caixa = _visivel(page, f"input[name='{name}']")
    try:
        caixa.wait_for(state="visible", timeout=10000)
        if caixa.get_attribute("aria-checked") == "true":
            return True
        try:
            caixa.click(timeout=2000)
        except Exception:
            # 1º teste real (07/10): no painel da Consulta o Playwright não
            # consegue rolar até a caixa ("element is outside of the viewport").
            # O click() do DOM dispara o mesmo evento que o Dojo escuta.
            caixa.evaluate("el => el.click()")
    except Exception as e:
        log(f"Não consegui marcar '{rotulo}': {e}", "error")
        return False
    fim = time.monotonic() + 3
    while time.monotonic() < fim:
        if caixa.get_attribute("aria-checked") == "true":
            log(f"'{rotulo}' marcado.", "success")
            return True
        page.wait_for_timeout(200)
    log(f"'{rotulo}' continua desmarcado depois do clique.", "error")
    return False


def _ir_para_monitor(page) -> None:
    """Monitor recarregado do zero: o que foi salvo antes (consulta de outra
    fila, perfil recém-criado) não pode vir junto — o Salvar poderia gravar
    por cima dele. Levanta exceção se não der; quem chama loga."""
    _aguardar_pagina_assentar(page)
    if "eventsearch" in page.url:
        page.reload()
    else:
        page.evaluate("destino => window.location.href = destino", _URL_MONITOR)
    _aguardar_pagina_assentar(page)


def _abrir_consulta(page, log) -> bool:
    """Monitor -> Consulta."""
    try:
        _ir_para_monitor(page)
        _visivel(page, _SEL_CONSULTA).click(timeout=30000)
        _visivel(page, f"input[name='{_TIPOS[0][0]}']").wait_for(
            state="visible", timeout=15000)
    except Exception as e:
        log(f"A tela de Consulta não abriu: {e}", "error")
        return False
    log("Consulta aberta.", "success")
    return True


def _escolher_departamento(page, log, fila: str) -> str | None:
    """Type-ahead: digitar não basta, o valor só vale escolhendo a sugestão.
    Devolve o texto da sugestão escolhida (a grafia do Assyst); None = falhou."""
    caixa = _visivel(page, _SEL_DEPARTAMENTO)
    try:
        caixa.wait_for(state="visible", timeout=10000)
        # ids do widget saem do input: <base>_textNode -> <base>_comboBox_...
        base = caixa.get_attribute("id").removesuffix("_textNode")
        try:
            caixa.click(timeout=2000)
        except Exception:
            caixa.focus()  # mesmo problema de rolagem das caixas de marcar
        caixa.press("Control+a")
        caixa.press("Delete")
        caixa.press_sequentially(fila, delay=60)
        page.wait_for_selector(f"[id='{base}_comboBox_dropdown']",
                               state="visible", timeout=15000)
    except Exception as e:
        log(f"A lista de sugestões do Departamento não abriu para {fila!r}: {e}", "error")
        return None

    opcoes = page.evaluate(_JS_OPCOES, f"{base}_comboBox_popup") or []
    alvo = _escolher_opcao(opcoes, fila)
    if alvo is None:
        vistas = "; ".join(o["texto"] for o in opcoes[:10]) or "nenhuma"
        log(f"Departamento {fila!r} não encontrado ou ambíguo. Sugestões: {vistas}", "error")
        return None
    item = page.locator(f"[id='{alvo['id']}']")
    try:
        item.click(timeout=10000)
    except Exception:
        try:
            item.dispatch_event("click")
        except Exception as e:
            log(f"Falha ao escolher o Departamento: {e}", "error")
            return None
    log(f"Departamento: {alvo['texto']}", "success")
    return alvo["texto"]


def _escolher_perfil(page, log, perfil: str, pode_faltar: bool = False) -> bool:
    """Texto das opções: '<NOME> --- <DONO>'. Casa pelo NOME, idêntico.

    `pode_faltar`: simulação com perfil NOVO — ele não foi salvo, então não
    está na lista; isso não é erro."""
    sel = _visivel(page, _SEL_PERFIL)
    try:
        opcoes = sel.evaluate(
            "s => [...s.options].map(o => ({value: o.value, texto: o.textContent}))")
    except Exception as e:
        log(f"Não achei o Perfil de coluna: {e}", "error")
        return False
    alvo = _norm(perfil)
    nomes = []
    for o in opcoes:
        nome = o["texto"].replace("\xa0", " ").split("---")[0].strip()
        if not nome:
            continue
        nomes.append(nome)
        if _norm(nome) == alvo:
            sel.select_option(value=o["value"])
            log(f"Perfil de coluna: {nome}", "success")
            return True
    if pode_faltar:
        log(f"Perfil {perfil!r} ainda não existe (simulação: não foi salvo) — "
            "seria escolhido aqui.", "info")
        return True
    log(f"Perfil de coluna {perfil!r} não existe. Disponíveis: {'; '.join(nomes)}", "error")
    return False


# ------------------------------------------------------------------ fluxo

def configurar_fila(page, log, fila: str, perfil: str, modo_teste: bool = False,
                    perfil_novo: bool = False) -> bool:
    """Cria a consulta da `fila` (Código = Nome = Departamento = fila).
    `perfil_novo`: o perfil foi criado neste mesmo pedido (ver criar_perfil)."""
    fila = fila.strip()

    # 1-3. Consulta + tipos
    if not _abrir_consulta(page, log):
        return False
    for name, rotulo in _TIPOS:
        if not _marcar(page, log, name, rotulo):
            return False

    # 4. Atribuição -> Departamento
    try:
        aba = page.locator(_SEL_ABA_ATRIBUICAO)
        aba.click(timeout=10000)
        page.wait_for_function(
            "s => document.querySelector(s)?.getAttribute('aria-selected') === 'true'",
            arg=_SEL_ABA_ATRIBUICAO, timeout=10000)
    except Exception as e:
        log(f"A aba 'Atribuição' não abriu: {e}", "error")
        return False
    escolhido = _escolher_departamento(page, log, fila)
    if escolhido is None:
        return False
    # Código/Nome com a grafia do cadastro ("2N CATI Sistemas"), não a digitada.
    if _norm(escolhido) == _norm(fila):
        fila = escolhido

    # 5. Somente Departamento -> Salvar (abre o pop-up; não grava)
    if not _marcar(page, log, *_SO_DEPARTAMENTO):
        return False
    try:
        page.locator(_SEL_SALVAR_CONSULTA).click(timeout=10000)
        _visivel(page, _SEL_CODIGO).wait_for(state="visible", timeout=15000)
    except Exception as e:
        log(f"O pop-up de salvar a consulta não abriu: {e}", "error")
        return False
    log("Pop-up da consulta aberto.", "success")

    # Pop-up já preenchido = é uma consulta EXISTENTE; salvar gravaria por cima.
    codigo = _visivel(page, _SEL_CODIGO)
    atual = codigo.input_value().strip()
    if atual:
        log(f"O pop-up veio com o Código {atual!r} preenchido — salvar alteraria "
            "uma consulta que já existe. Parei sem salvar.", "error")
        return False

    # 6-8. Código, Nome, Perfil, caixas
    try:
        codigo.fill(fila)
        _visivel(page, _SEL_NOME).fill(fila)
    except Exception as e:
        log(f"Não consegui preencher Código/Nome: {e}", "error")
        return False
    if not _escolher_perfil(page, log, perfil, pode_faltar=modo_teste and perfil_novo):
        return False
    for name, rotulo in _OPCOES_POPUP:
        if not _marcar(page, log, name, rotulo):
            return False

    if modo_teste:
        log("MODO TESTE: pop-up preenchido. Cancelando ANTES de Salvar — "
            "nada foi gravado.", "status")
        try:
            page.locator(_SEL_CANCELAR_POPUP).click(timeout=5000)
        except Exception:
            pass  # a próxima fila recarrega a página de qualquer jeito
        return True

    # Salvar do pop-up — o único passo que grava.
    try:
        page.locator(_SEL_SALVAR_POPUP).click(timeout=10000)
    except Exception as e:
        log(f"Erro ao clicar em Salvar: {e}", "error")
        return False
    try:
        _visivel(page, _SEL_CODIGO).wait_for(state="hidden", timeout=15000)
    except Exception:
        log("O pop-up não fechou após Salvar — o Assyst pode ter recusado "
            "(ex.: Código já existe). Confira a tela.", "error")
        return False
    log(f"Fila {fila!r} configurada.", "success")
    return True


# ------------------------------------------------------- perfil de coluna
# Mesma página do monitor: Colunas (seta ▼) -> Novo -> passar as colunas para
# 'selecionadas' NA ORDEM -> Salvar (topo; só abre o pop-up) -> Código/Nome ->
# Salvar do pop-up (o que grava). HTML real mandado pelo usuário em 07/10.

# Decisão do usuário (07/10): o técnico só pede "configure a fila X"; o
# perfil tem nome e colunas FIXOS. Criado na 1ª vez, reaproveitado depois.
PERFIL_PADRAO = "Meu Perfil"
# Nomes EXATOS da lista 'Colunas disponíveis', NA ORDEM (lista do usuário, 07/10).
# "Nº" é o ordinal (º), como no Assyst — não o símbolo de grau (°).
COLUNAS_PADRAO: list[str] = [
    "Nº de ref.",
    "Nome de usuário afetado",
    "Nome da seção",
    "Nível de escalação",
    "Ícone do Relógio Parado de ANS",
    "Edifício",
    "Nome do Usuário Atribuído",
    "Nome de item A",
    "Nome de categoria",
    "Data da última ação",
    "Nome da última ação realizada",
    "Nome do DPS Atribuído",
]

_SEL_COLUNAS_SETA = "#columnProfileList_arrow"
_SEL_MENU_NOVO = "td.dijitMenuItemLabel:text-is('Novo')"
# `curColSel` é id DUPLICADO na tela (também no 'Classificar por'): só por name.
_SEL_DISPONIVEIS = "select[name='availableColumnsSelect']"
_SEL_SELECIONADAS = "select[name='currentColumnsSelect']"
_SEL_MOVER = "#columnProfileSelectColumn"          # o '>' (os rótulos dos outros não batem com o id)
_SEL_PERFIL_FORM = "form[name='ManageColumnProfileForm']"
_SEL_PERFIL_CODIGO = f"{_SEL_PERFIL_FORM} input[name='shortCode']"
_SEL_PERFIL_NOME = f"{_SEL_PERFIL_FORM} input[name='name']"
_SEL_PERFIL_SALVAR = "[id='columnProfileProperties_okButton']"
_SEL_PERFIL_CANCELAR = "[id='columnProfileProperties_cancelButton']"

_JS_OPCOES_SELECT = (
    "s => [...s.options].map(o => ({value: o.value,"
    " texto: o.textContent.replace(/\s+/g, ' ').trim()}))")


def _opcoes_select(page, sel: str) -> list[dict]:
    return _visivel(page, sel).evaluate(_JS_OPCOES_SELECT)


def _mapear_colunas(log, disponiveis: list[dict], colunas: list[str]) -> list[dict] | None:
    """Nome dito -> opção da lista. Tudo conferido ANTES de mexer na tela:
    um nome errado no meio deixaria o perfil pela metade."""
    import difflib
    por_nome = {_norm(o["texto"]): o for o in disponiveis}
    achadas, faltam = [], []
    for c in colunas:
        o = por_nome.get(_norm(c))
        if o:
            achadas.append(o)
        else:
            parecidas = difflib.get_close_matches(
                c, [o["texto"] for o in disponiveis], n=3, cutoff=0.6)
            faltam.append(f"{c!r}" + (f" (parecidas: {', '.join(parecidas)})" if parecidas else ""))
    if faltam:
        log(f"Coluna(s) não encontrada(s): {'; '.join(faltam)}. Nada foi alterado.", "error")
        return None
    return achadas


def _abrir_perfil_novo(page, log, nome: str) -> str:
    """Colunas ▼ -> Novo. Antes, confere na própria lista se o perfil já
    existe. Devolve "aberto", "existe" ou "erro"."""
    try:
        _ir_para_monitor(page)
        page.locator(_SEL_COLUNAS_SETA).click(timeout=30000)
        novo = _visivel(page, _SEL_MENU_NOVO)
        novo.wait_for(state="visible", timeout=10000)
    except Exception as e:
        log(f"O menu de Colunas não abriu: {e}", "error")
        return "erro"
    existentes = page.locator("td.dijitMenuItemLabel:visible").all_inner_texts()
    if any(_norm(t) == _norm(nome) for t in existentes):
        page.keyboard.press("Escape")
        return "existe"
    try:
        novo.click(timeout=10000)
        _visivel(page, _SEL_DISPONIVEIS).wait_for(state="visible", timeout=15000)
    except Exception as e:
        log(f"A tela de novo Perfil de coluna não abriu: {e}", "error")
        return "erro"
    log("Novo Perfil de coluna aberto.", "success")
    return "aberto"


def _passar_coluna(page, log, opcao: dict, posicao: int) -> bool:
    """Seleciona UMA coluna em 'disponíveis' e clica '>'. Confere que ela
    entrou no FIM de 'selecionadas' — é isso que garante a ordem."""
    try:
        _visivel(page, _SEL_DISPONIVEIS).select_option(value=opcao["value"])
        page.locator(_SEL_MOVER).click(timeout=5000)
    except Exception as e:
        log(f"Não consegui passar a coluna {opcao['texto']!r}: {e}", "error")
        return False
    fim = time.monotonic() + 5
    while time.monotonic() < fim:
        atuais = _opcoes_select(page, _SEL_SELECIONADAS)
        if len(atuais) == posicao + 1 and atuais[-1]["value"] == opcao["value"]:
            return True
        page.wait_for_timeout(200)
    log(f"A coluna {opcao['texto']!r} não entrou na posição {posicao + 1}.", "error")
    return False


def garantir_perfil(page, log, modo_teste: bool = False,
                    nome: str = PERFIL_PADRAO, colunas: list[str] = COLUNAS_PADRAO) -> str | None:
    """Garante o Perfil de coluna `nome` com `colunas` NA ORDEM (Código =
    Nome = nome). Se já existe (pedido anterior), REAPROVEITA sem mexer.

    Devolve "existente", "criado", "simulado" (montado e cancelado) ou None
    (falhou — o motivo já foi logado)."""
    nome = nome.strip()
    if not colunas:
        log("A lista de colunas padrão ainda não foi definida (COLUNAS_PADRAO).", "error")
        return None
    situacao = _abrir_perfil_novo(page, log, nome)
    if situacao == "existe":
        log(f"Perfil de coluna {nome!r} já existe — reaproveitado.", "success")
        return "existente"
    if situacao != "aberto":
        return None

    disponiveis = _opcoes_select(page, _SEL_DISPONIVEIS)
    escolhidas = _mapear_colunas(log, disponiveis, colunas)
    if escolhidas is None:
        return None
    if _opcoes_select(page, _SEL_SELECIONADAS):
        log("O perfil novo já veio com colunas selecionadas — parei sem mexer.", "error")
        return None

    for i, opcao in enumerate(escolhidas):
        if not _passar_coluna(page, log, opcao, i):
            return None
    ordem = [o["value"] for o in _opcoes_select(page, _SEL_SELECIONADAS)]
    if ordem != [o["value"] for o in escolhidas]:
        log("A ordem das colunas na tela não bate com a pedida — parei sem salvar.", "error")
        return None
    log(f"{len(escolhidas)} coluna(s) na ordem pedida.", "success")

    # Salvar do topo: só abre o pop-up 'Propriedades'.
    try:
        _visivel(page, _SEL_SALVAR_CONSULTA).click(timeout=10000)
        codigo = _visivel(page, _SEL_PERFIL_CODIGO)
        codigo.wait_for(state="visible", timeout=15000)
    except Exception as e:
        log(f"O pop-up de salvar o perfil não abriu: {e}", "error")
        return None
    atual = codigo.input_value().strip()
    if atual:
        log(f"O pop-up veio com o Código {atual!r} — salvar alteraria um perfil "
            "que já existe. Parei sem salvar.", "error")
        return None
    try:
        codigo.fill(nome)
        _visivel(page, _SEL_PERFIL_NOME).fill(nome)
    except Exception as e:
        log(f"Não consegui preencher Código/Nome do perfil: {e}", "error")
        return None

    if modo_teste:
        log("MODO TESTE: perfil montado. Cancelando ANTES de Salvar — nada foi gravado.",
            "status")
        try:
            page.locator(_SEL_PERFIL_CANCELAR).click(timeout=5000)
        except Exception:
            pass
        return "simulado"

    try:
        page.locator(_SEL_PERFIL_SALVAR).click(timeout=10000)
        _visivel(page, _SEL_PERFIL_CODIGO).wait_for(state="hidden", timeout=15000)
    except Exception:
        log("O pop-up do perfil não fechou após Salvar — o Assyst pode ter "
            "recusado. Confira a tela.", "error")
        return None
    log(f"Perfil de coluna {nome!r} criado.", "success")
    return "criado"
