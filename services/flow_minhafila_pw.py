"""
services/flow_minhafila_pw.py — leitura da grade "Minha Fila" em Playwright.

Portado do link fornecido pelo usuario: uma pesquisa salva no proprio Assyst
(queryProfileId=4 / columnProfileId=2) que lista os chamados da fila do
tecnico logado. So LEITURA, mesmo espirito do flow_sla_pw.py.

POR QUE POR CLASSE CSS E NAO POR IDX: no flow_sla_pw a grade de HISTORICO nao
e reordenavel pelo usuario, entao ler por indice de coluna (`celulas[2]`) e
seguro. Aqui a grade E a pesquisa de eventos, e o proprio usuario pode aplicar
um filtro ou arrastar uma coluna no Assyst — o que muda a ORDEM das colunas
sem mudar a CLASSE de cada celula (`eventReferenceCell`,
`affectedUserNameCell`, `department_section_nameCell` sao fixas). Por isso a
extracao aqui mira a classe, nao a posicao.

GRADE VIRTUALIZADA: mesma familia do Dojo Grid do kb_manager_pw.py — so as
linhas visiveis existem no DOM. A diferenca e que o kb_manager para na
PRIMEIRA linha que bate com o texto procurado; aqui precisamos de TODAS as
linhas da fila, entao rolamos ate o fim da grade acumulando por referencia
(dedup), em vez de parar no primeiro achado.
"""

import time

from services.browser_pw import _aguardar_pagina_assentar

_URL_MINHA_FILA = (
    "https://cati.tjce.jus.br/assystweb/application.do"
    "#eventsearch%2FEventSearchDelegatingDispatchAction.do%3Fdispatch%3DloadQuery"
    "%26showInMonitor%3Dtrue%26context%3Dselect%26queryProfileForm.queryProfileId%3D4"
    "%26queryProfileForm.columnProfileId%3D2"
)

# Titulo do painel quando a consulta CERTA esta carregada (confirmado em tela
# real: "Chamados Atribuídos a mim | Pesquisa de evento"). E o sinal que
# faltava para distinguir "Minha Fila" da "Fila Geral" -- ambas produzem uma
# grade valida, so o titulo denuncia qual das duas realmente carregou.
_SEL_TITULO = "#eventPaneTitleValue"
_TITULO_MINHA_FILA = "Chamados Atribuídos a mim"

# Quantas vezes tenta trocar o hash antes de desistir. Existe porque a troca
# de hash por cima da SPA ja logada nem sempre "pega" na primeira -- rever a
# nota em ler_fila.
_MAX_TENTATIVAS_NAVEGACAO = 3

_SEL_SCROLLBOX = ".dojoxGridScrollbox"

# SO ".dojoxGridRow", SEM exigir ".eventGridRow". Essa classe extra parecia um
# bom filtro (aparecia em toda linha de um teste anterior com a Fila Geral),
# mas em teste real com "Minha Fila" uma das duas linhas validas NAO tinha
# essa classe (so a linha selecionada tinha) -- confirmado lendo o HTML bruto
# da grade. Ou seja, "eventGridRow" nao e um marcador confiavel de "isto e uma
# linha de chamado"; ".dojoxGridRow" sozinho e. Nao ha risco de pegar lixo:
# a extracao ja descarta qualquer linha sem "referencia" preenchida.
_SEL_LINHA = ".dojoxGridRow"

# Teto de rolagens. A passo de 80% da altura visivel, isso cobre uma fila bem
# maior que qualquer fila real de tecnico sem risco de laco infinito.
_MAX_SCROLLS = 300

_JS_LER_PAGINA = """
(scrollbox) => {
    const linhas = scrollbox.querySelectorAll('.dojoxGridRow');
    const texto = el => (el ? el.textContent.trim() : '');
    const dados = Array.from(linhas).map(linha => ({
        referencia: texto(linha.querySelector('td.eventReferenceCell')),
        afetado:    texto(linha.querySelector('td.affectedUserNameCell')),
        secao:      texto(linha.querySelector('td.department_section_nameCell')),
    }));
    return {
        dados,
        scrollTop: scrollbox.scrollTop,
        clientHeight: scrollbox.clientHeight,
        scrollHeight: scrollbox.scrollHeight,
        totalLinhasNaTela: document.querySelectorAll('.dojoxGridRow').length,
        fim: scrollbox.scrollTop + scrollbox.clientHeight >= scrollbox.scrollHeight - 2,
    };
}
"""

_JS_ROLAR = "el => { el.scrollTop += el.clientHeight * 0.8; }"


def _titulo_atual(page) -> str:
    try:
        return page.locator(_SEL_TITULO).first.inner_text(timeout=2000).strip()
    except Exception:
        return ""  # painel ainda nao montado / DOM em transicao


def ler_fila(page, log) -> list[dict] | None:
    """Navega para 'Minha Fila' e devolve [{referencia, afetado, secao}, ...].

    Assume que o login ja foi feito (sessao ativa) — quem orquestra
    (bot/services/minhafila_service.py) cuida disso, mesmo desenho do
    extrair_historico_chamado no flow_sla_pw.

    None em falha tecnica (login, ou a consulta certa nunca carregou). Lista
    vazia quando a fila realmente esta vazia — os dois casos precisam ser
    distinguidos pelo chamador para nao reportar "fila vazia" quando a
    automacao quebrou.
    """
    log("Abrindo Minha Fila...", "status")

    # NAO fazer navegacao cheia (about:blank + goto direto pro hash): tentado
    # e devolveu tela em branco do Assyst -- a aplicacao nao inicializa direito
    # quando o hash de "eventsearch" ja esta presente no carregamento inicial
    # (headless/automacao; o "abrir o link numa aba nova" que funciona para
    # humanos deve passar por um caminho que nao reproduzimos aqui).
    #
    # Trocar so o hash por cima da SPA ja logada (como o _navegar_para_chamado_pw
    # faz) carrega uma grade real, mas NEM SEMPRE a certa -- em teste real veio
    # a Fila Geral em vez de Minha Fila. O TITULO do painel (#eventPaneTitleValue)
    # denuncia qual consulta carregou de fato, entao em vez de confiar que o
    # hash "pegou", conferimos o titulo e RETENTAMOS a troca se nao bater --
    # mesma logica do _esperar_chamado_carregado (espera por MUDANCA/sinal real,
    # nao por presenca ou por tempo fixo).
    _aguardar_pagina_assentar(page)

    titulo = ""
    for tentativa in range(1, _MAX_TENTATIVAS_NAVEGACAO + 1):
        page.evaluate("destino => window.location.href = destino", _URL_MINHA_FILA)
        _aguardar_pagina_assentar(page)

        fim = time.monotonic() + 15
        while time.monotonic() < fim:
            titulo = _titulo_atual(page)
            if _TITULO_MINHA_FILA in titulo:
                break
            time.sleep(0.3)

        if _TITULO_MINHA_FILA in titulo:
            break
        log(f"A tela carregou '{titulo or '(vazio)'}' em vez de Minha Fila; "
            f"tentando de novo... ({tentativa}/{_MAX_TENTATIVAS_NAVEGACAO})", "info")

    if _TITULO_MINHA_FILA not in titulo:
        log(f"Nao consegui abrir Minha Fila -- a tela ficou em "
            f"'{titulo or '(vazio)'}' apos {_MAX_TENTATIVAS_NAVEGACAO} tentativas.",
            "error")
        return None

    scrollbox = page.locator(_SEL_SCROLLBOX).first
    try:
        scrollbox.wait_for(state="visible", timeout=20000)
    except Exception as e:
        log(f"A grade da fila nao carregou: {e}", "error")
        return None

    try:
        page.locator(_SEL_LINHA).first.wait_for(state="attached", timeout=10000)
    except Exception:
        log("Fila vazia.", "info")
        return []

    coletados: dict[str, dict] = {}
    scroll_anterior = -1
    total_anterior = -1
    leituras_estaveis = 0

    # NAO confia em `fim` (scrollHeight/clientHeight) sozinho na PRIMEIRA
    # leitura: quando toda a fila cabe num viewport so (sem precisar rolar), o
    # Dojo ja reporta o scrollHeight final, mas pode ainda estar pintando as
    # linhas — ler nesse instante capturava so a primeira. Uma unica leitura
    # extra ("nao cresceu desde a ultima vez") ainda nao bastou em modo
    # HEADLESS: confirmado em producao (bot sem janela) que o Dojo pode levar
    # mais que 400ms para pintar a linha seguinte, e duas leituras exatamente
    # nesse intervalo veem a MESMA contagem parcial e concluem "estabilizou"
    # cedo demais. Por isso agora exige 2 leituras CONSECUTIVAS sem
    # crescimento (nao so uma comparacao pontual) com um intervalo maior.
    for indice in range(_MAX_SCROLLS):
        pagina = page.eval_on_selector(_SEL_SCROLLBOX, _JS_LER_PAGINA)
        for item in pagina["dados"]:
            ref = item["referencia"]
            if ref:
                coletados[ref] = item

        # DIAGNOSTICO TEMPORARIO
        log(f"[debug] leitura {indice + 1}: {len(pagina['dados'])} linha(s) no "
            f"scrollbox, {pagina['totalLinhasNaTela']} .dojoxGridRow na tela "
            f"inteira | clientHeight={pagina['clientHeight']} "
            f"scrollHeight={pagina['scrollHeight']} scrollTop={pagina['scrollTop']} "
            f"fim={pagina['fim']} | coletados={len(coletados)}", "info")

        sem_novidade = (len(coletados) == total_anterior
                         and pagina["scrollTop"] == scroll_anterior)
        total_anterior = len(coletados)
        scroll_anterior = pagina["scrollTop"]

        leituras_estaveis = leituras_estaveis + 1 if sem_novidade else 0
        if leituras_estaveis >= 2:
            break

        page.eval_on_selector(_SEL_SCROLLBOX, _JS_ROLAR)
        page.wait_for_timeout(700)  # tempo para o Dojo desenhar as novas linhas

    log(f"{len(coletados)} chamado(s) na fila.", "success")
    return list(coletados.values())
