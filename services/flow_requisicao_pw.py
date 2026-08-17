"""
services/flow_requisicao_pw.py — Fluxo "Requisição de Serviço" em Playwright.

Abre chamados DO ZERO (o Desmembramento duplica um chamado existente; aqui nao ha
chamado-pai). Caminho no Assyst: navegar para a tela de Requisição, preencher os
campos e clicar em Salvar.

Seletores confirmados por reconhecimento em tela viva (2026-08-02, teste_requisicao.py):
  - Prefixo do formulario  -> 'ES3' na sessao capturada, mas SEMPRE descoberto da
    propria pagina (`descobrir_prefixos`); nunca escrito por extenso. Em LOTE ha
    mais de um formulario no DOM ao mesmo tempo — ver `abrir_tela_requisicao`.
  - Lista do type-ahead    -> `<campo>_comboBox_dropdown` (pop-up) contendo
    `<campo>_comboBox_popup` (menu); itens = `..._popup0`, `..._popup1`, ...
    'Opções anteriores'/'Mais opções' sao PAGINACAO, nao resultados.
  - Botao Salvar           -> '#btlogEvent' (o MESMO ja usado em producao pelo
    Desmembramento — por isso nao e peca nova).

A ORDEM DE PREENCHIMENTO e a ordem do catalogo (`CAMPOS`), que e a ordem visual da
tela. Isso nao e estetica, sao duas dependencias reais:
  - 'Usuário afetado' vem primeiro porque escolhe-lo faz o Assyst preencher
    Seção/Grupo/Edifício/Sala sozinho — um valor explicito para esses campos
    precisa ser aplicado DEPOIS, ou o auto-preenchimento o sobrescreve;
  - 'Categoria' so e LIBERADA pelo Assyst depois que 'Item' e escolhido (nasce
    `readonly`), e no catalogo Item ja vem antes. Ver `_esperar_editavel`.

Ver memoria: project_flow_requisicao, project_ckeditor_fix, project_checkpoint_sinais.
"""

import dataclasses
import hashlib
import time

from services.assyst_common import _URL_REQUISICAO, _so_o_nome
from services.browser_pw import _aguardar_pagina_assentar, _preencher_descricao_pw
from services.requisicao_campos import (
    CAMPOS, CHECKBOX, CKEDITOR, DATA_HORA, LOOKUP, ORDEM_COLUNAS, POR_CHAVE,
    SEPARADOR, TEXTO,
    descobrir_prefixos, id_campo, id_campo_hora, id_dropdown,
    id_lookup_dialog_cancelar, id_lookup_dialog_resultados_contagem,
    id_lookup_dialog_usar_selecionado, id_opcoes,
)

# Valor de catalogo usado quando o Item B nao localiza o tombo digitado (ver
# `_preencher_item_b`). Mesmo texto usado nos exemplos de `EXEMPLOS_PREENCHIDOS`
# (state/requisicao_state.py) — e um valor real, ja confirmado na tela.
_ITEM_B_NAO_LOCALIZADO = "IC NÃO LOCALIZADO"

# Os `except Exception` deste modulo sao largos DE PROPOSITO, como nos demais
# fluxos: o Playwright so levanta PWTimeout na espera estourada — strict mode,
# elemento desprendido no meio do clique e target fechado sao
# `playwright.sync_api.Error`. Estreitar a porta faria uma linha ruim derrubar o
# lote inteiro em vez de falhar so ela.

_SEL_SALVAR = "#btlogEvent"
_SEL_TITULO = "h1#contentPaneTitle"


@dataclasses.dataclass
class RequisicaoCriada:
    """O que UMA requisição produziu. `None` continua sendo o unico sinal de falha.

    Existe porque a tabela de resultados precisa de DUAS informacoes: o numero e
    quem e o usuario afetado. Antes a aba mostrava o valor que o operador COLOU
    (a matricula), que e o que ela tinha em maos — o nome so aparece depois, na
    tela, quando o type-ahead resolve a matricula.
    """

    numero: str   # "" no modo_teste (preencheu e nao salvou, entao nao ha numero)
    usuario: str  # nome do Usuario afetado; cai para a matricula se nao der para ler

# Valores de planilha que significam "marque este checkbox".
_VERDADEIROS = {"1", "x", "s", "sim", "true", "v", "verdadeiro", "y", "yes"}

# Pausa entre teclas do caminho LENTO (so o fallback usa; ver `_escrever`).
_DELAY_TECLA_MS = 120

# Campos cuja escolha faz o ASSYST preencher OUTROS campos sozinho, e qual campo
# serve de SINAL de que a resposta chegou:
#   Usuário afetado -> Seção e Edifício
#   Categoria       -> Impacto e Urgência (confirmado pelo usuario em 2026-08-02)
# Esperamos o SINAL, nao um tempo. Antes havia um `wait_for_timeout(1500)` cego aqui:
# queimava 1,5 s mesmo quando a resposta chegava em 200 ms, e mesmo assim podia ser
# curto demais numa rede lenta. Espera cega erra dos dois lados.
#
# EDIFICIO ENTROU NA LISTA POR UM MOTIVO CONCRETO (log do usuario, 2026-08-02): o
# Assyst SEMPRE preenche o Edifício ao escolher o Usuário afetado — com o edificio
# certo ou com "Por Definir" (o generico). Essa resposta chegava DEPOIS de a Seção
# chegar, ou seja, depois de o fluxo ja ter comecado a digitar no Edifício: o
# auto-preenchimento caia por cima do texto digitado, a lista nao abria, e o campo
# custava 9 s (6 s de timeout + a repeticao tecla a tecla). Esperar o Edifício
# assentar ANTES de escrever nele mata a corrida.
_AUTOCOMPLETAM: dict[str, tuple[str, ...]] = {
    "usuario_afetado": ("secao", "edificio"),
    "categoria": ("impacto", "urgencia"),
}


# ---------------------------------------------------------------- utilitarios

def _norm(texto: str) -> str:
    """Compara texto de tela com texto de planilha sem tropecar em espaco/caixa."""
    return " ".join((texto or "").split()).casefold()


# Coleta os itens do menu de sugestoes. Feito em JS (e nao com locators) porque o
# que separa RESULTADO de PAGINACAO e o formato do id: `..._popup0` e resultado,
# `..._popup_next` ('Mais opções') e botao de pagina.
_JS_OPCOES = r"""
(idMenu) => {
    const menu = document.getElementById(idMenu);
    if (!menu) return null;
    const out = [];
    menu.querySelectorAll("[id^='" + idMenu + "']").forEach(el => {
        const resto = el.id.slice(idMenu.length);
        if (!/^\d+$/.test(resto)) return;   // pula _previous / _next (paginacao)
        out.push({
            id: el.id,
            texto: (el.textContent || '').replace(/\s+/g, ' ').trim(),
        });
    });
    return out;
}
"""


def _titulo(page) -> str:
    """Titulo do painel agora ("" se ainda nao montado / DOM em transicao)."""
    try:
        return page.locator(_SEL_TITULO).inner_text().strip()
    except Exception:
        return ""


def _capturar_numero(page, titulo_antes: str, timeout_s: float = 15.0) -> str | None:
    """Numero da requisição criada. `None` = o Assyst NAO trocou de tela.

    Espera o titulo MUDAR (e passar a conter digitos), nao so existir. Ler o
    titulo logo depois de clicar em Salvar devolveria o titulo da tela ANTERIOR
    enquanto a SPA ainda monta a nova — mesma corrida ja corrigida na captura do
    numero do chamado filho no Desmembramento.

    O `None` importa: se o Assyst RECUSAR o salvamento (validacao), a tela nao
    muda, e sem esta distincao o fluxo reportaria "criada" para um chamado que
    nao existe. Falso sucesso e pior que falso erro aqui — o operador so
    descobriria o chamado faltando depois, sem saber qual linha refazer.

    Nao reusa o `_capturar_numero_filho_pw` so para o log nao falar em "chamado
    filho" — aqui nao existe pai.
    """
    fim = time.monotonic() + timeout_s
    while time.monotonic() < fim:
        atual = _titulo(page)
        if atual and atual != titulo_antes and any(c.isdigit() for c in atual):
            return atual.split(" ")[0].strip()
        page.wait_for_timeout(300)
    return None


def _escolher_opcao(opcoes: list[dict], valor: str) -> dict | None:
    """Decide QUAL sugestao corresponde ao valor pedido — ou nenhuma.

    A regra e deliberadamente conservadora, na ordem:
      1. texto identico ao valor (o caso de Impacto, Urgência, Item...);
      2. **valor seguido de '('** — o discriminador da MATRICULA. Buscar '5244'
         traz '5244', '52447', '5277896'...; so o usuario certo tem o parentese
         logo depois da matricula ('5244(FULANO DE TAL)'). Sem esta regra, o item
         certo e "ambiguo" e o fluxo aborta sempre;
      3. um unico item que COMECA com o valor;
      4. a lista inteira tem um item so.
    Ambiguidade NAO e resolvida no chute: varios candidatos => None, e o chamador
    aborta mostrando as opcoes. Escolher errado aqui abriria um chamado para a
    pessoa errada, e isso ninguem descobre olhando log de sucesso.
    """
    alvo = _norm(valor)
    exatos = [o for o in opcoes if _norm(o["texto"]) == alvo]
    if exatos:
        return exatos[0]
    marcados = [o for o in opcoes if _norm(o["texto"]).startswith(alvo + "(")]
    if len(marcados) == 1:
        return marcados[0]
    comecam = [o for o in opcoes if _norm(o["texto"]).startswith(alvo)]
    if len(comecam) == 1:
        return comecam[0]
    if not comecam and len(opcoes) == 1:
        return opcoes[0]
    return None


# ------------------------------------------------------------------- a tela

def _valor_usuario_afetado(page, prefixo: str) -> str | None:
    """Valor do 'Usuário afetado' do formulario `prefixo`.

    `None` = o campo nao existe ou nao esta VISIVEL nesta tela. A visibilidade
    importa: o Dojo deixa formularios antigos e templates escondidos no DOM, e
    um template escondido tem os campos vazios — ele passaria por "formulario em
    branco" sem ser a tela que o operador esta vendo.
    """
    sel = id_campo(prefixo, POR_CHAVE["usuario_afetado"])
    try:
        caixa = page.locator(sel)
        if caixa.count() == 0 or not caixa.first.is_visible():
            return None
        return caixa.first.input_value().strip()
    except Exception:
        return None  # DOM em transicao: quem chama reavalia no proximo ciclo


def _prefixo_em_branco(page) -> str | None:
    """Prefixo do formulario de Requisição EM BRANCO que esta na tela agora.

    O criterio e o 'Usuário afetado' estar VAZIO. Uma Requisição nova nasce sem
    ele; a tela de um chamado ja salvo o tem preenchido. E o unico jeito de
    distinguir as duas, porque no id as duas sao `ManageEventForm_<PREFIXO>_...`.
    """
    for prefixo in descobrir_prefixos(page):
        if _valor_usuario_afetado(page, prefixo) == "":
            return prefixo
    return None


def _diagnostico_formularios(page, log) -> None:
    """Diz QUAIS formularios ficaram na tela. So roda quando ja falhou.

    Sem isto, "a tela nao abriu" nao distingue 'nao navegou' de 'navegou mas
    ficou na tela do chamado anterior' — e cada hipotese custa um lote inteiro
    para testar.
    """
    try:
        achados = [f"{p}='{_valor_usuario_afetado(page, p)}'"
                   for p in descobrir_prefixos(page)]
    except Exception as e:
        log(f"[DIAG] nao consegui inspecionar os formularios: {e}", "error")
        return
    log(f"[DIAG] formularios na tela (prefixo='Usuário afetado'; None = campo "
        f"escondido): {' / '.join(achados) or 'nenhum'}", "info")


def abrir_tela_requisicao(page, log, timeout_s: float = 30.0) -> str | None:
    """Navega para a tela de Requisição EM BRANCO e devolve o prefixo dela.

    Retorna None se a tela nao abriu — sem prefixo nao ha nada a fazer, e melhor
    parar aqui do que montar seletores que nunca vao casar.

    CORRIDA QUE ESTA FUNCAO EXISTE PARA MATAR (bug do lote, relatado em teste com
    usuarios: a 2a requisição saía com o 'Usuário afetado' vazio). Antes,
    esperava-se `[id^='ManageEventForm_']` ficar `attached`. So que a tela do
    chamado RECEM-CRIADO tambem e um `ManageEventForm_` e continua no DOM
    enquanto a SPA monta a nova: o wait retornava NA HORA, `descobrir_prefixo`
    lia o prefixo da tela VELHA, e o fluxo ia digitar num formulario que nao era
    o da tela. E o mesmo erro de "presenca em vez de mudanca" ja corrigido no
    `_esperar_chamado_carregado` e na captura do numero do filho.

    O criterio agora e positivo: esperar aparecer um formulario com o 'Usuário
    afetado' VAZIO E VISIVEL — isto e, uma Requisição em branco de verdade.
    """
    log("Abrindo a tela de Requisição de Serviço...", "status")

    # A pagina pode chegar aqui AINDA CARREGANDO (o caso classico e vir direto do
    # login): trocar o location.href no meio de uma navegacao pendente PERDE a
    # rota. Mesma licao ja aplicada em _navegar_para_chamado_pw.
    _aguardar_pagina_assentar(page)
    try:
        page.evaluate("destino => window.location.href = destino", _URL_REQUISICAO)
    except Exception as e:
        log(f"A tela de Requisição nao abriu: {e}", "error")
        return None

    fim = time.monotonic() + timeout_s
    while time.monotonic() < fim:
        prefixo = _prefixo_em_branco(page)
        if prefixo is not None:
            log(f"Formulario carregado (prefixo {prefixo}).", "success")
            return prefixo
        page.wait_for_timeout(300)

    log(f"A Requisição em branco nao apareceu em {timeout_s:.0f}s.", "error")
    _diagnostico_formularios(page, log)
    return None


# ------------------------------------------------------- preenchimento por tipo

def _esperar_editavel(page, log, sel: str, campo) -> bool:
    """Espera o input aceitar digitacao (sair de `readonly`/`disabled`).

    Existe por causa da CATEGORIA: ela e um type-ahead comum, mas o Assyst so a
    LIBERA depois que o Item e escolhido — antes disso o input nasce `readonly`
    (foi assim que ela apareceu no HTML capturado com a tela em branco, o que me
    fez achar, errado, que era um campo especial de seleção por dialogo).

    Como a liberacao vem da resposta do Assyst ao Item, ela nao e instantanea: sem
    esta espera o fluxo digitaria num campo ainda bloqueado e o valor sumiria sem
    erro nenhum. `wait_for_function` observa o DOM ate soltar, em vez de dormir um
    tempo fixo torcendo para dar certo.
    """
    try:
        page.wait_for_function(
            "s => { const el = document.querySelector(s);"
            " return el && !el.readOnly && !el.disabled; }",
            arg=sel, timeout=15000)
        return True
    except Exception:
        dica = (f" Ele so libera depois de '{POR_CHAVE[campo.depende_de].rotulo}' — "
                "confira se esse campo foi preenchido antes."
                if campo.depende_de in POR_CHAVE else "")
        log(f"'{campo.rotulo}' continua bloqueado para digitacao.{dica}", "error")
        return False


def _escrever(caixa, texto: str, tecla_a_tecla: bool) -> None:
    """Poe `texto` na caixa de busca, limpando o que houver antes.

    RAPIDO (padrao): `fill()` de tudo menos o ultimo caractere + UMA tecla de
    verdade. O type-ahead do Dojo nao acumula teclas — ele LE o valor do input
    quando busca, e a busca e disparada por um evento de teclado com debounce
    proprio. Entao uma tecla real no fim vale pelas N: o widget vai buscar pelo
    texto inteiro. Custo deixa de depender do tamanho do valor.

    LENTO (`tecla_a_tecla=True`): digita tudo, com pausa entre as teclas — o
    caminho provado na captura. Fica como rede de seguranca, nao como padrao.
    """
    caixa.click()
    caixa.press("Control+a")
    caixa.press("Delete")
    if tecla_a_tecla:
        caixa.press_sequentially(texto, delay=_DELAY_TECLA_MS)
        return
    if len(texto) > 1:
        caixa.fill(texto[:-1])
    caixa.press_sequentially(texto[-1])


def _digitar_e_listar(page, log, prefixo, campo, texto: str) -> list[dict] | None:
    """Digita `texto` no lookup e devolve as sugestoes que apareceram.

    None = nao deu para digitar ou a lista nao abriu (erro ja logado);
    [] = a lista abriu vazia (o valor nao existe).

    Tenta primeiro o caminho RAPIDO e, se a lista nao abrir, refaz tecla a tecla.
    O fallback e o que permite ganhar o tempo sem apostar: no pior caso gasta-se
    uma digitacao a mais; no caso comum, economiza-se o tamanho inteiro do valor.
    """
    sel = id_campo(prefixo, campo)
    if not _esperar_editavel(page, log, sel, campo):
        return None

    for tecla_a_tecla in (False, True):
        try:
            caixa = page.locator(sel).first
            caixa.wait_for(state="visible", timeout=15000)
            _escrever(caixa, texto, tecla_a_tecla)
        except Exception as e:
            log(f"Nao consegui digitar em '{campo.rotulo}': {e}", "error")
            return None

        # A primeira tentativa espera pouco: se o modo rapido nao serviu para este
        # widget, e melhor descobrir logo e refazer do que segurar 15 s.
        espera = 15000 if tecla_a_tecla else 6000
        try:
            page.wait_for_selector(
                id_dropdown(prefixo, campo), state="visible", timeout=espera)
        except Exception:
            if not tecla_a_tecla:
                log(f"'{campo.rotulo}': a lista nao abriu no modo rapido; "
                    "repetindo tecla a tecla...", "info")
                continue
            log(f"'{campo.rotulo}': a lista de sugestoes nao abriu para {texto!r}.",
                "error")
            return None

        return page.evaluate(_JS_OPCOES, id_opcoes(prefixo, campo)) or []


def _clicar_sugestao(page, log, campo, alvo: dict) -> bool:
    """Clica no item da lista. Clique nativo; `dispatch` como rede de seguranca."""
    seletor = f"[id='{alvo['id']}']"
    try:
        page.locator(seletor).click(timeout=10000)
        return True
    except Exception:
        # Itens de menu do Dojo as vezes ignoram o clique nativo (o handler esta
        # no 'ondijitclick'); o dispatch e o mesmo recurso ja usado no 'Continuar'
        # do Desmembramento.
        try:
            page.locator(seletor).dispatch_event("click")
            return True
        except Exception as e:
            log(f"'{campo.rotulo}': falha ao clicar na sugestao: {e}", "error")
            return False


def _mesmo_valor(atual: str, pedido: str) -> bool:
    """O que esta no campo ja e o que se quer?

    Aceita a forma como o Assyst RENDERIZA o valor escolhido, nao so o texto
    digitado: `905245` casa com `905245(RIBAMAR TORRES CORREIA LIMA)`. Mesma regra
    do parentese usada para escolher a sugestao.
    """
    a, p = _norm(atual), _norm(pedido)
    return bool(a) and (a == p or a.startswith(p + "("))


def _valor_de(page, prefixo, campo) -> str:
    """Valor que o campo tem AGORA ("" se vazio ou se o DOM estiver em transicao)."""
    try:
        return page.locator(id_campo(prefixo, campo)).first.input_value().strip()
    except Exception:
        return ""


def _nome_usuario(page, prefixo, fallback: str) -> str:
    """Nome do Usuário afetado, lido da tela DEPOIS que o type-ahead resolveu.

    O operador cola a matricula (`905245`); o Assyst renderiza o campo escolhido
    como `905245(RIBAMAR TORRES CORREIA LIMA)`. O corte fica no `_so_o_nome`
    (assyst_common), compartilhado com a Analise de SLA.

    Cai para o `fallback` (o valor colado) quando o campo esta vazio ou o DOM
    esta em transicao. Ler isto NUNCA pode derrubar o fluxo — e enfeite de
    tabela, nao etapa da criacao.
    """
    return _so_o_nome(_valor_de(page, prefixo, POR_CHAVE["usuario_afetado"])) or fallback


def _esperar_autocompletar(page, log, prefixo, campo, timeout_s: float = 6.0) -> None:
    """Depois de um campo que dispara auto-preenchimento, espera a RESPOSTA chegar.

    Sai assim que os campos-sinal ficam preenchidos — tipicamente em alguns
    centesimos. O `timeout_s` e so o teto: nao achando o sinal, SEGUE em frente (a
    checagem de obrigatorios antes de salvar e o portao de verdade). Nunca trava o
    fluxo, no maximo o atrasa quando o Assyst nao respondeu.
    """
    alvos = _AUTOCOMPLETAM.get(campo.chave)
    if not alvos:
        return
    fim = time.monotonic() + timeout_s
    while time.monotonic() < fim:
        if all(_valor_de(page, prefixo, POR_CHAVE[a]) for a in alvos):
            return
        page.wait_for_timeout(150)
    # Nao e erro: so diagnostico. Se aparecer junto de "obrigatorio vazio" mais
    # adiante, ja se sabe onde a resposta do Assyst se perdeu.
    log(f"'{campo.rotulo}': o auto-preenchimento nao confirmou em {timeout_s:.0f}s; "
        "seguindo.", "info")


def _valor_gravado(page, sel: str, timeout_s: float = 8.0) -> str:
    """Espera o input ficar preenchido e devolve o valor ("" se nunca ficou).

    O widget grava o valor DEPOIS do clique, e as vezes limpa o campo por um
    instante antes de escrever o texto definitivo — uma leitura unica pode cair
    justo nesse buraco.
    """
    fim = time.monotonic() + timeout_s
    while True:
        try:
            valor = page.locator(sel).first.input_value().strip()
        except Exception:
            valor = ""  # DOM em transicao: reavalia no proximo ciclo
        if valor or time.monotonic() >= fim:
            return valor
        page.wait_for_timeout(200)


def selecionar_lookup(page, log, prefixo, campo, valor: str) -> bool:
    """Preenche um campo type-ahead: digita, espera a lista e ESCOLHE o item.

    O `fill()` nao serve aqui: ele troca o texto do input sem passar pelo widget,
    e o Assyst grava o valor de verdade so quando um item da lista e escolhido —
    salvar depois de um `fill()` gravaria o campo VAZIO. Por isso digitamos tecla
    a tecla (e o que dispara a busca) e clicamos no item.
    """
    sel = id_campo(prefixo, campo)

    # ATALHO: o Assyst ja pos ali o valor pedido? Entao nao ha nada a fazer.
    # Acontece o tempo todo no Edifício, que vem do Usuário afetado — e quando ele
    # ja vem certo, digitar de novo so gasta uma ida ao servidor para chegar no
    # mesmo lugar. Vale para qualquer lookup (Seção idem).
    atual = _valor_de(page, prefixo, campo)
    if _mesmo_valor(atual, valor):
        log(f"{campo.rotulo}: {atual} (ja preenchido pelo Assyst)", "success")
        return True

    opcoes = _digitar_e_listar(page, log, prefixo, campo, valor)
    if opcoes is None:
        return False
    alvo = _escolher_opcao(opcoes, valor)

    # SEGUNDA TENTATIVA com o parentese colado no fim. Se a busca do Assyst
    # aceitar o '(', ela ja devolve so o item certo; se ignorar a pontuacao,
    # perdemos so uma digitada e a regra do `_escolher_opcao` decide igual.
    if alvo is None and not valor.endswith("("):
        log(f"'{campo.rotulo}': {valor!r} deu lista ambigua; refinando com '('...",
            "info")
        opcoes2 = _digitar_e_listar(page, log, prefixo, campo, valor + "(")
        if opcoes2:
            opcoes = opcoes2
            alvo = _escolher_opcao(opcoes, valor)

    if alvo is None:
        vistas = " | ".join(o["texto"] for o in opcoes[:8])
        log(f"'{campo.rotulo}': {valor!r} nao identifica UM item. Opcoes na tela: "
            f"{vistas}. Refine o valor (se houver 'Mais opções', ha ainda mais "
            "resultados alem destes).", "error")
        return False

    if not _clicar_sugestao(page, log, campo, alvo):
        return False

    # CONFIRMACAO: o campo tem que ter ficado preenchido. Sem esta checagem o
    # fluxo "daria certo" com o campo vazio e so o Assyst reclamaria no salvar.
    #
    # A confirmacao ESPERA em laco em vez de ler uma vez depois de um sleep: o
    # widget grava o valor DEPOIS do clique, e tempo fixo aqui e sempre aposta.
    gravado = _valor_gravado(page, sel)
    if not gravado:
        # Segunda tentativa de clique: itens de menu Dojo as vezes ignoram um
        # clique que chega enquanto a lista ainda esta se montando.
        log(f"'{campo.rotulo}': o valor nao apareceu; clicando de novo...", "info")
        if _clicar_sugestao(page, log, campo, alvo):
            gravado = _valor_gravado(page, sel, timeout_s=4.0)

    if not gravado:
        log(f"'{campo.rotulo}': cliquei em {alvo['texto']!r} mas o campo ficou vazio.",
            "error")
        return False

    log(f"{campo.rotulo}: {gravado}", "success")
    return True


def _preencher_item_b(page, log, prefixo, campo, valor: str) -> bool:
    """Preenche 'Item B' — igual ao lookup comum, mas com uma rede de segurança
    especifica deste campo.

    NEM TODO VALOR DE ITEM B E UM TOMBO. Muitas vezes e so uma palavra normal, e
    o esperado e ela SER encontrada pelo caminho comum (dropdown de sugestoes,
    igual a qualquer outro lookup). Mas quando o valor E um tombo de patrimonio
    (digitado como '*<numero>', ex. '*332255'), o campo entra num modo de busca
    por CODIGO EXATO com TRES desfechos possiveis, confirmados em tela viva
    (2026-08-13):
      1. Acha um resultado exato -> RESOLVE SOZINHO, sem abrir nada (nem
         dropdown, nem dialogo) — o campo so passa a mostrar o valor resolvido
         (ex.: '*332255' vira 'C091SJURI332255'). Esse e o caminho mais comum
         para um tombo que existe.
      2. Nao acha nada -> abre um DIALOGO MODAL de busca avancada, sem nenhuma
         relacao com o tombo digitado (o campo 'Nome' de dentro dele vem com o
         coringa '*' por padrao — e uma busca generica da categoria, nao um
         resultado filtrado). O contador `resultsCount` vem '0'. Nao ha nada
         util pra automacao extrair dali: a saida e fechar e usar o valor de
         catalogo `_ITEM_B_NAO_LOCALIZADO`.
      3. (Defensivo, nao confirmado em tela — o botao existe pra isso) Acha UM
         resultado mas nao resolve sozinho -> mesmo dialogo, `resultsCount=='1'`,
         com a linha ja pre-selecionada (`automaticRowSelection`); clicar OK
         aplica o resultado.

    A DIGITACAO TEM QUE SER TECLA A TECLA (`tecla_a_tecla=True`), NAO o modo
    rapido (`fill()`) usado nos demais lookups. Foi a causa raiz de um bug ja
    visto ao vivo: com o modo rapido, um tombo EXISTENTE (*332255) abria o
    dialogo mesmo achando 1 resultado — o `fill()` nao dispara os mesmos
    eventos de teclado que o widget usa para reconhecer a busca por codigo
    exato. Tecla a tecla reproduz o que o usuario faz na mao e resolve direto,
    sem popup nenhum, exatamente como descrito por ele.

    Reusa os pedacos do `selecionar_lookup`/`_digitar_e_listar` (escolha de
    opcao, clique, confirmacao) em vez de duplicar aquele fluxo inteiro.
    """
    sel = id_campo(prefixo, campo)

    # ATALHO: mesmo criterio do selecionar_lookup — se ja esta certo, nada a fazer.
    atual = _valor_de(page, prefixo, campo)
    if _mesmo_valor(atual, valor):
        log(f"{campo.rotulo}: {atual} (ja preenchido pelo Assyst)", "success")
        return True

    if not _esperar_editavel(page, log, sel, campo):
        return False

    try:
        caixa = page.locator(sel).first
        caixa.wait_for(state="visible", timeout=15000)
        _escrever(caixa, valor, tecla_a_tecla=True)
        caixa.press("Tab")  # gatilho da busca, igual ao passo manual
    except Exception as e:
        log(f"Nao consegui digitar em '{campo.rotulo}': {e}", "error")
        return False

    sel_dropdown = id_dropdown(prefixo, campo)
    sel_cancelar = id_lookup_dialog_cancelar(campo)
    try:
        page.wait_for_selector(f"{sel_dropdown}, {sel_cancelar}",
                               state="visible", timeout=5000)
    except Exception:
        # NEM dropdown NEM dialogo apareceram — o caminho feliz do tombo: o
        # widget resolveu sozinho. Confirma olhando o campo, em vez de supor.
        gravado = _valor_gravado(page, sel, timeout_s=3.0)
        if gravado:
            log(f"{campo.rotulo}: {gravado} (resolvido direto, sem popup)", "success")
            return True
        log(f"'{campo.rotulo}': nem a lista de sugestoes, nem o dialogo de busca, "
            f"nem um valor resolvido apareceram para {valor!r}.", "error")
        return False

    if page.locator(sel_cancelar).count() > 0 and page.locator(sel_cancelar).is_visible():
        contagem = page.evaluate(
            "id => { const el = document.getElementById(id);"
            " return el ? el.textContent.trim() : null; }",
            id_lookup_dialog_resultados_contagem())

        if contagem == "1":
            # Defensivo (nao reproduzido em tela): 1 resultado, mas o widget nao
            # resolveu sozinho. A linha vem pre-selecionada; OK aplica ela.
            log(f"'{campo.rotulo}': dialogo abriu com 1 resultado para {valor!r}; "
                "usando o selecionado.", "info")
            sel_ok = id_lookup_dialog_usar_selecionado(campo)
            try:
                page.locator(sel_ok).click(timeout=5000)
            except Exception as e:
                log(f"Nao consegui clicar em OK no dialogo do '{campo.rotulo}': {e}",
                    "error")
                return False
            gravado = _valor_gravado(page, sel, timeout_s=4.0)
            if not gravado:
                log(f"'{campo.rotulo}': cliquei em OK mas o campo ficou vazio.", "error")
                return False
            log(f"{campo.rotulo}: {gravado}", "success")
            return True

        log(f"'{campo.rotulo}': {valor!r} nao foi localizado (dialogo com "
            f"resultsCount={contagem!r}); fechando e usando "
            f"'{_ITEM_B_NAO_LOCALIZADO}'.", "info")
        try:
            page.locator(sel_cancelar).click(timeout=5000)
        except Exception as e:
            log(f"Nao consegui fechar o dialogo de busca do '{campo.rotulo}': {e}",
                "error")
            return False
        return selecionar_lookup(page, log, prefixo, campo, _ITEM_B_NAO_LOCALIZADO)

    # Dropdown normal abriu (valor sem cara de tombo, ex. uma palavra): segue o
    # caminho comum de escolha de sugestao.
    opcoes = page.evaluate(_JS_OPCOES, id_opcoes(prefixo, campo)) or []
    alvo = _escolher_opcao(opcoes, valor)
    if alvo is None:
        vistas = " | ".join(o["texto"] for o in opcoes[:8])
        log(f"'{campo.rotulo}': {valor!r} nao identifica UM item. Opcoes na tela: "
            f"{vistas}.", "error")
        return False
    if not _clicar_sugestao(page, log, campo, alvo):
        return False
    gravado = _valor_gravado(page, sel)
    if not gravado:
        log(f"'{campo.rotulo}': cliquei em {alvo['texto']!r} mas o campo ficou vazio.",
            "error")
        return False
    log(f"{campo.rotulo}: {gravado}", "success")
    return True


def preencher_texto(page, log, prefixo, campo, valor: str) -> bool:
    """Input comum — aqui `fill()` basta (nao ha widget guardando o valor)."""
    try:
        caixa = page.locator(id_campo(prefixo, campo)).first
        caixa.wait_for(state="visible", timeout=15000)
        caixa.fill(valor)
        log(f"{campo.rotulo}: {valor}", "success")
        return True
    except Exception as e:
        log(f"Erro ao preencher '{campo.rotulo}': {e}", "error")
        return False


def marcar_checkbox(page, log, prefixo, campo, valor: str) -> bool:
    """Marca/desmarca conforme o valor ('sim', '1', 'x'... = marcar)."""
    marcar = _norm(valor) in _VERDADEIROS
    sel = id_campo(prefixo, campo)
    try:
        caixa = page.locator(sel).first
        caixa.wait_for(state="visible", timeout=15000)
        if marcar:
            caixa.check(timeout=10000)
        else:
            caixa.uncheck(timeout=10000)
    except Exception:
        # O <input> real do dijit fica sob o quadradinho estilizado; quando o
        # check() nao alcanca, o clique no widget resolve.
        try:
            page.locator(sel).first.dispatch_event("click")
        except Exception as e:
            log(f"Erro ao marcar '{campo.rotulo}': {e}", "error")
            return False
    log(f"{campo.rotulo}: {'marcado' if marcar else 'desmarcado'}", "success")
    return True


def preencher_data_hora(page, log, prefixo, campo, valor: str) -> bool:
    """Par data + hora ('dd/mm/aaaa hh:mm'; so a data tambem serve).

    Sao dois `dijitDateTextBox`/`dijitTimeTextBox` com id GLOBAL (sem prefixo).
    Digitamos em vez de `fill()` e saimos com Tab: o Dojo converte o texto no
    valor real quando o campo perde o foco. O Escape antes fecha o calendario que
    o widget abre ao receber o clique — aberto, ele engoliria o Tab.
    """
    partes = valor.split()
    data, hora = partes[0], (partes[1] if len(partes) > 1 else "")
    ok = True
    for sel, texto in ((id_campo(prefixo, campo), data),
                       (id_campo_hora(prefixo, campo), hora)):
        if not texto:
            continue
        try:
            caixa = page.locator(sel).first
            caixa.wait_for(state="visible", timeout=15000)
            caixa.click()
            caixa.press("Control+a")
            caixa.press_sequentially(texto, delay=60)
            caixa.press("Escape")
            caixa.press("Tab")
        except Exception as e:
            log(f"Erro ao preencher '{campo.rotulo}' ({texto}): {e}", "error")
            ok = False
    if ok:
        log(f"{campo.rotulo}: {valor}", "success")
    return ok


def _preencher_campo(page, log, prefixo, campo, valor: str) -> bool:
    """Despacha para o preenchedor certo conforme o TIPO do campo."""
    if campo.chave == "item_b":
        # Rede de seguranca do tombo (ver `_preencher_item_b`): so este campo,
        # nao o LOOKUP generico — os outros 16 nao tem o dialogo modal.
        return _preencher_item_b(page, log, prefixo, campo, valor)
    if campo.tipo == LOOKUP:
        return selecionar_lookup(page, log, prefixo, campo, valor)
    if campo.tipo == TEXTO:
        return preencher_texto(page, log, prefixo, campo, valor)
    if campo.tipo == CHECKBOX:
        return marcar_checkbox(page, log, prefixo, campo, valor)
    if campo.tipo == DATA_HORA:
        return preencher_data_hora(page, log, prefixo, campo, valor)
    if campo.tipo == CKEDITOR:
        return _preencher_descricao_pw(page, log, valor)
    log(f"Tipo de campo desconhecido em '{campo.chave}': {campo.tipo}", "error")
    return False


# --------------------------------------------------------------- entrada/lote

def _obrigatorios_vazios(page, prefixo, espera_s: float = 6.0) -> list[str]:
    """Rotulos dos campos obrigatorios que continuam VAZIOS na tela.

    ESPERA antes de desistir porque metade deles nao e digitada por nos: Seção
    vem do Usuário afetado, e Impacto/Urgência vem da Categoria. Esses valores
    chegam pela resposta do Assyst, com atraso. Ler uma vez so, logo depois de
    preencher, acusaria "obrigatorio vazio" num formulario que na verdade estava
    completo um instante depois — e o fluxo abortaria um chamado bom.
    """
    fim = time.monotonic() + espera_s
    while True:
        vazios = [c.rotulo for c in CAMPOS
                  if c.obrigatorio and not _valor_de(page, prefixo, c)]
        if not vazios or time.monotonic() >= fim:
            return vazios
        page.wait_for_timeout(500)


def parse_linha(linha: str, ordem=ORDEM_COLUNAS) -> dict[str, str]:
    """Converte uma linha 'a; b; c' no dicionario {chave_do_campo: valor}.

    O contrato e POSICIONAL e sem cabecalho (decisao do usuario): o 1o valor e o
    1o campo de `ordem`, e assim por diante. Diferente do CSV do Desmembramento,
    que tem cabecalho. Valores vazios sao DESCARTADOS — campo em branco significa
    "nao mexer", e nao "apagar".

    Separador = `;` (ver SEPARADOR): Resumo e Descrição sao texto livre, e uma
    virgula digitada sem querer deslocaria todos os campos seguintes.

    Levanta se a linha tiver valores DEMAIS: silenciar isso criaria o chamado com
    os campos trocados, sem erro nenhum aparecer.
    """
    desconhecidas = [c for c in ordem if c not in POR_CHAVE]
    if desconhecidas:
        raise ValueError(f"Colunas fora do catalogo: {desconhecidas}")
    valores = [v.strip() for v in linha.split(SEPARADOR)]
    if len(valores) > len(ordem):
        rotulos = ", ".join(POR_CHAVE[c].rotulo for c in ordem)
        raise ValueError(
            f"A linha tem {len(valores)} valores, mas sao {len(ordem)} colunas "
            f"({rotulos}). Se algum texto tem '{SEPARADOR}', tire-o. Linha: {linha!r}")
    return {chave: valor for chave, valor in zip(ordem, valores) if valor}


def parse_entrada(texto: str, ordem=ORDEM_COLUNAS) -> list[dict[str, str]]:
    """Converte o bloco colado (uma requisição por linha) numa lista de valores.

    Linhas em branco sao ignoradas. O erro cita o NUMERO DA LINHA, porque quem
    cola 40 linhas precisa saber qual consertar.
    """
    requisicoes = []
    for n, linha in enumerate(texto.splitlines(), start=1):
        if not linha.strip():
            continue
        try:
            requisicoes.append(parse_linha(linha, ordem))
        except ValueError as e:
            raise ValueError(f"Linha {n}: {e}") from e
    return requisicoes


def _chave_checkpoint(texto: str) -> str:
    """Gera a chave do checkpoint a partir do TEXTO COLADO inteiro.

    A Requisição não tem chamado-pai pra ancorar a chave (ela cria do zero) —
    por isso a chave é derivada do próprio conteúdo colado (hash, não o texto
    puro: pode ter dezenas de linhas, e um nome de arquivo não aguenta isso).

    CONSEQUÊNCIA ACEITA (decisão do usuário, 2026-08-13): mudar UMA linha do
    bloco colado — mesmo só um espaço — vira "lote novo" pro checkpoint, sem
    ligação com o anterior. Efeito colateral bom: como a chave já embute o
    conteúdo, não existe o CASO 4 do Desmembramento (mesma chave, `total`
    diferente) — aqui, conteúdo diferente É chave diferente, sempre.
    """
    return "req_" + hashlib.sha1(texto.strip().encode("utf-8")).hexdigest()[:16]


def criar_requisicao(page, log, valores: dict[str, str],
                     modo_teste: bool = False) -> RequisicaoCriada | None:
    """Abre UMA Requisição de Serviço. Retorna o que ela produziu.

    Retorna:
      - um `RequisicaoCriada` (com `numero` e `usuario`) quando foi criada;
      - `None` em QUALQUER falha — campo que nao entrou, obrigatorio vazio, ou
        Salvar que nao trocou de tela (o Assyst recusou). Nada e salvo pela metade;
      - no `modo_teste`, um `RequisicaoCriada` com `numero=""` (preencheu e nao
        salvou, entao nao ha numero).

    `modo_teste=True` preenche tudo e PARA antes de salvar, deixando a tela na
    tela para conferencia. E o mesmo de-risking usado no Iniciar Atendimento.
    """
    prefixo = abrir_tela_requisicao(page, log)
    if prefixo is None:
        return None

    desconhecidas = [c for c in valores if c not in POR_CHAVE]
    if desconhecidas:
        log(f"Campos fora do catalogo: {desconhecidas}", "error")
        return None

    # Dependencia entre campos, conferida ANTES de mexer na tela: pedir Categoria
    # sem Item nao tem como dar certo, e falhar aqui e mais claro do que falhar no
    # meio do preenchimento com meia tela ja escrita.
    for chave in valores:
        dep = POR_CHAVE[chave].depende_de
        if dep and not valores.get(dep):
            log(f"'{POR_CHAVE[chave].rotulo}' exige '{POR_CHAVE[dep].rotulo}' "
                "preenchido — o Assyst so o libera depois disso.", "error")
            return None

    # Ordem do CATALOGO, nao a ordem em que o usuario mandou: o Usuário afetado
    # tem que ir antes de Seção/Grupo/Edifício/Sala, senao o auto-preenchimento
    # do Assyst apaga o que foi digitado.
    for campo in CAMPOS:
        valor = valores.get(campo.chave)
        if not valor:
            continue
        if not _preencher_campo(page, log, prefixo, campo, valor):
            log(f"Abortado em '{campo.rotulo}' — nada foi salvo.", "error")
            return None
        # Espera a resposta do Assyst antes do proximo campo — pelo SINAL, nao por
        # tempo. Sem isso o campo seguinte disputa a tela com o auto-preenchimento.
        _esperar_autocompletar(page, log, prefixo, campo)

    # Obrigatorios: conferidos NA TELA, nao na entrada. Impacto e Urgência sao
    # obrigatorios (rotulo vermelho) mas nao estao na lista que o operador
    # preenche — a suspeita e que venham de outro campo (Categoria/Item). Checar a
    # entrada abortaria um preenchimento que na verdade esta completo; checar a
    # tela responde a pergunta certa: falta alguma coisa AGORA?
    vazios = _obrigatorios_vazios(page, prefixo)

    # Lido AGORA, com o formulario ainda na tela: depois do Salvar a SPA troca de
    # tela e o campo pode nao existir mais no DOM.
    usuario = _nome_usuario(page, prefixo, valores.get("usuario_afetado", "--"))

    if modo_teste:
        if vazios:
            log(f"MODO TESTE: obrigatorios ainda vazios: {', '.join(vazios)}", "error")
        log("MODO TESTE: formulario preenchido, NAO salvei.", "status")
        return RequisicaoCriada(numero="", usuario=usuario)

    if vazios:
        log(f"Nao salvei: campos obrigatorios vazios na tela: {', '.join(vazios)}",
            "error")
        return None

    # O titulo ANTES do clique e a referencia da mudanca de tela (ver _capturar_numero).
    titulo_antes = _titulo(page)
    try:
        page.click(_SEL_SALVAR, timeout=20000)
    except Exception as e:
        log(f"Erro ao salvar a requisição: {e}", "error")
        return None

    numero = _capturar_numero(page, titulo_antes)
    if numero is None:
        log("Cliquei em Salvar mas a tela nao mudou — o Assyst provavelmente "
            "recusou o salvamento. Confira a tela: a requisição NAO foi criada.",
            "error")
        return None

    log(f"Requisição criada: {numero} ({usuario})", "success")
    return RequisicaoCriada(numero=numero, usuario=usuario)
