"""
services/requisicao_campos.py — Catalogo dos campos da tela "Requisição de Serviço".

Extraido do HTML real da tela (arquivo `html_requisicao` na raiz, capturado em
2026-07-30). NAO tem navegador nem reflex: e so a descricao dos campos, para o
fluxo e a pagina falarem a mesma lingua.

DUAS COISAS QUE MANDAM NA ESTRUTURA:

1. **O prefixo do formulario e DINAMICO.** Todos os ids sao
   `ManageEventForm_<PREFIXO>_<sufixo>` e o editor de descricao e
   `rt<PREFIXO>_formattedRemarks`. Na captura o prefixo era `ES3`, mas e o mesmo
   padrao do `rtEC65_formattedRemarks` do fluxo de Desmembramento — ou seja, muda
   por tela/sessao. Por isso NENHUM id aqui e escrito por extenso: use
   `descobrir_prefixo(page)` uma vez e depois `id_campo(prefixo, campo)`.
   (Os campos de data/hora fogem disso: tem id global `txt_...`, sem prefixo.)

2. **A maioria dos campos e LOOKUP TYPE-AHEAD**, nao `<select>` de HTML. Sao 17, todos
   com a mesma estrutura: uma tabela `.typeAheadContainer` contendo `.typeAheadInput`
   (o `<input>` `..._textNode`) e `.typeAheadOptions`. Digita-se parte do valor, o
   Dojo abre a lista e escolhe-se um item. Preencher via `fill()` NAO seleciona nada —
   o valor de verdade so e gravado quando o item da lista e escolhido. Mesma armadilha
   do CKEditor (escrever no DOM sem atualizar o modelo do widget).
   A LISTA de sugestoes nao existe no HTML estatico (o Dojo a cria na hora), mas
   ja foi CAPTURADA em tela viva (2026-08-02) e virou `id_dropdown`/`id_opcoes`
   aqui embaixo: os ids sao derivados do proprio campo, sem nada aleatorio.

**OBRIGATORIOS:** a tela marca 5 rotulos em vermelho — Usuário afetado, Seção, Item,
Impacto e Urgência (ver `obrigatorio` em cada Campo). Como Seção vem preenchida pelo
Usuário afetado, na pratica sao 4 que o operador precisa informar.
"""

import dataclasses
import re

# Tipos de campo — determinam COMO preencher, e cada um vira uma acao no fluxo.
LOOKUP = "lookup"        # widget Dojo: digitar + escolher na lista
TEXTO = "texto"          # input comum: fill() basta
CKEDITOR = "ckeditor"    # iframe do CKEditor: digitar (ver _preencher_descricao_pw)
CHECKBOX = "checkbox"    # marcar/desmarcar
DATA_HORA = "data_hora"  # par de inputs (data + hora), id global sem prefixo


@dataclasses.dataclass(frozen=True)
class Campo:
    chave: str      # nome curto usado na configuracao da ordem das colunas
    rotulo: str     # rotulo exato da tela (para logs e para a ajuda na UI)
    sufixo: str     # sufixo do id, depois de `ManageEventForm_<PREFIXO>_`
    tipo: str
    obrigatorio: bool = False      # rotulo em vermelho na tela
    depende_de: str = ""           # chave do campo que HABILITA este (ver Categoria)
    observacao: str = ""


# Ordem = ordem visual do formulario (util para a ajuda da UI).
CAMPOS: tuple[Campo, ...] = (
    Campo("usuario_afetado", "Usuário afetado", "affectedUser", LOOKUP, obrigatorio=True,
          observacao="Ao escolher, o Assyst preenche sozinho Seção/Grupo/Edifício/Sala."),
    Campo("telefone", "Telefone", "affectedUserTelephone", TEXTO),
    Campo("ramal", "Ramal", "affectedUserTelephoneExtension", TEXTO),
    Campo("secao", "Seção", "section", LOOKUP, obrigatorio=True,
          observacao="Obrigatorio, mas vem preenchido pelo Usuário afetado."),
    Campo("grupo", "Grupo", "department", LOOKUP),
    Campo("edificio", "Edifício", "building", LOOKUP),
    Campo("sala", "Sala", "room", LOOKUP),
    Campo("resumo", "Resumo", "shortDescription", TEXTO),
    Campo("descricao", "Descrição", "formattedRemarks", CKEDITOR,
          observacao="id e `rt<PREFIXO>_formattedRemarks` (fora do padrao ManageEventForm_)."),
    Campo("produto", "Produto", "itemAProduct", LOOKUP),
    Campo("item", "Item", "itemA", LOOKUP, obrigatorio=True),
    Campo("produto_b", "Produto B", "itemBProduct", LOOKUP),
    Campo("item_b", "Item B", "itemB", LOOKUP),
    Campo("categoria", "Categoria", "eventBuilder", LOOKUP, depende_de="item",
          observacao="Type-ahead comum, mas o input nasce `readonly` e so LIBERA "
                     "depois que o Item e escolhido. No HTML capturado (tela em "
                     "branco) ele aparece bloqueado — nao e campo especial."),
    Campo("impacto", "Impacto", "seriousness", LOOKUP, obrigatorio=True),
    Campo("urgencia", "Urgência", "priority", LOOKUP, obrigatorio=True),
    Campo("processo", "Processo", "templateProcess", LOOKUP),
    Campo("iniciar_processo", "Iniciar processo?", "startProcess", CHECKBOX),
    Campo("retorno_necessario", "Retorno Necessário", "callbackRequired", CHECKBOX),
    Campo("indicador_inatividade", "Indicador de inatividade", "downFlag", CHECKBOX),
    Campo("grupo_atribuido", "Grupo de Serv. Atribuído", "assignedServDept", LOOKUP),
    Campo("usuario_atribuido", "Usuário Atribuído", "assignee", LOOKUP),
    Campo("notas_retorno", "Notas do retorno", "callbackRemark", TEXTO),
    Campo("solicitado_para", "Solicitado para", "txt_requiredByDate", DATA_HORA),
    Campo("inicio_agendado", "Início agendado", "txt_scheduledStartDate", DATA_HORA),
    Campo("fim_agendado", "Fim agendado", "txt_scheduledEndDate", DATA_HORA),
    Campo("email_telefone_confirmados", "E-mail e telefone confimados",
          "webCustomPropertyValue_1408", CHECKBOX),
    Campo("modelos_adicionais", "Modelos Adicionais Incidentes/Problemas",
          "addModelEvent", LOOKUP),
    Campo("mudancas_modelo", "Mudanças modelo adicionais", "addChangeModelEvent", LOOKUP),
)

POR_CHAVE: dict[str, Campo] = {c.chave: c for c in CAMPOS}

# ORDEM DAS COLUNAS DA ENTRADA (definida pelo usuario em 2026-08-02).
# O contrato e POSICIONAL e sem cabecalho: o 1o valor da linha e o 1o campo daqui.
# Sao 9 campos; os demais do catalogo existem na tela mas nao entram na planilha.
# Impacto e Urgência NAO estao aqui de proposito: a Categoria os preenche.
ORDEM_COLUNAS: tuple[str, ...] = (
    "usuario_afetado",
    "edificio",
    "resumo",
    "descricao",
    "item",
    "item_b",
    "categoria",
    "grupo_atribuido",
    "usuario_atribuido",
)

# SEPARADOR das colunas. Ponto e virgula, nao virgula: Resumo e Descricao sao texto
# livre, e uma virgula digitada sem querer deslocaria todos os campos seguintes —
# o chamado seria criado errado, sem nenhum erro aparecer. Decisao do usuario.
SEPARADOR = ";"

# Campo que sempre existe na tela — serve de sonda para achar o prefixo.
_SONDA = "shortDescription"
_PADRAO_PREFIXO = re.compile(r"ManageEventForm_([A-Za-z0-9]+)_" + _SONDA)


def descobrir_prefixos(page) -> list[str]:
    """TODOS os prefixos de formulario presentes na tela, na ordem do DOM.

    Normalmente e um so. Mas o Assyst e uma SPA: ao navegar para uma Requisição
    NOVA a partir de um chamado ja aberto, a tela anterior continua no DOM
    enquanto a nova e montada — e a tela de um chamado salvo TAMBEM e um
    `ManageEventForm_`. Nesse instante existem dois prefixos, e pegar o primeiro
    (o que `descobrir_prefixo` faz) e pegar o VELHO.

    Quem precisa do formulario em branco tem que escolher entre os candidatos,
    nao aceitar o primeiro — ver `_prefixo_em_branco` no flow_requisicao_pw.
    """
    ids = page.eval_on_selector_all(
        "[id^='ManageEventForm_']", "els => els.map(e => e.id)")
    prefixos: list[str] = []
    for id_ in ids:
        m = _PADRAO_PREFIXO.match(id_)
        if m and m.group(1) not in prefixos:
            prefixos.append(m.group(1))
    return prefixos


def descobrir_prefixo(page) -> str:
    """Le da PROPRIA tela o prefixo do formulario (ex.: 'ES3').

    Procura o id do campo Resumo, que existe em qualquer Requisição, e extrai o
    trecho do meio. Levanta se nao achar — melhor falhar aqui, alto e claro, do
    que seguir montando seletores que nunca vao casar.

    CUIDADO: devolve o PRIMEIRO prefixo do DOM. Só serve quando ha uma tela so
    (o teste_requisicao.py, que abre a Requisição direto depois do login). Num
    LOTE, use `descobrir_prefixos` e escolha o formulario em branco.
    """
    prefixos = descobrir_prefixos(page)
    if prefixos:
        return prefixos[0]
    ids = page.eval_on_selector_all(
        "[id^='ManageEventForm_']", "els => els.map(e => e.id)")
    raise RuntimeError(
        "Nao foi possivel descobrir o prefixo do formulario de Requisicao "
        f"(nenhum id casou com ManageEventForm_<PREFIXO>_{_SONDA}). "
        f"Ids vistos: {ids[:10]}")


def id_campo(prefixo: str, campo: Campo) -> str:
    """Monta o seletor CSS do INPUT do campo, para o prefixo descoberto na tela."""
    if campo.tipo == CKEDITOR:
        return f"#rt{prefixo}_{campo.sufixo}"
    if campo.tipo == DATA_HORA:
        return f"#{campo.sufixo}Date"          # o par e ...Date / ...Time
    if campo.tipo == CHECKBOX:
        return f"#{prefixo}_{campo.sufixo}"    # checkbox nao leva ManageEventForm_
    if campo.tipo == LOOKUP:
        # No type-ahead o id "limpo" e a <table class="typeAheadContainer">; quem
        # recebe a digitacao e o <input> interno, com sufixo `_textNode`.
        return f"#ManageEventForm_{prefixo}_{campo.sufixo}_textNode"
    # TEXTO: aqui o id "limpo" JA E o <input> — `_textNode` e exclusividade do
    # lookup. Aplicar `_textNode` a todo mundo foi o que fez telefone, ramal,
    # resumo e notas_retorno (os 4 unicos campos TEXTO) aparecerem como
    # "nao existe" no reconhecimento em tela viva de 2026-08-02.
    return f"#ManageEventForm_{prefixo}_{campo.sufixo}"


def _base_lookup(prefixo: str, campo: Campo) -> str:
    """Prefixo comum dos ids do widget type-ahead (SEM o '#' de seletor CSS)."""
    if campo.tipo != LOOKUP:
        raise ValueError(f"{campo.chave} nao e um lookup")
    return f"ManageEventForm_{prefixo}_{campo.sufixo}_comboBox"


def id_dropdown(prefixo: str, campo: Campo) -> str:
    """Seletor do POP-UP de sugestoes (`div.dijitPopup`), criado pelo Dojo ao digitar.

    Capturado em tela viva: digitar em `affectedUser` fez nascer
    `..._affectedUser_comboBox_dropdown` (o container posicionado na tela) e,
    dentro dele, `..._comboBox_popup` (o menu). Esperamos o DROPDOWN ficar
    visivel, porque e ele que carrega o estado de aberto/fechado.
    """
    return f"#{_base_lookup(prefixo, campo)}_dropdown"


def id_opcoes(prefixo: str, campo: Campo) -> str:
    """Id do MENU de sugestoes. Os itens sao esse id + um numero: `..._popup0`,
    `..._popup1`, ... — `_popup_previous`/`_popup_next` sao a paginacao
    ('Opções anteriores' / 'Mais opções'), nao resultados."""
    return f"{_base_lookup(prefixo, campo)}_popup"


def id_lookup_dialog_cancelar(campo: Campo) -> str:
    """Botao Cancelar do dialogo de busca MODAL que alguns lookups abrem quando o
    valor digitado nao e localizado (ex.: um tombo de patrimonio no Item B, que
    normalmente e digitado como '*<numero>').

    SEM PREFIXO — diferente de tudo mais neste modulo. Os campos do formulario
    levam `ManageEventForm_<PREFIXO>_...`, mas o id deste botao vem do
    `lookupProperty` do widget (`<sufixo>.lookup._cancelbutton`), que nao carrega
    o prefixo do formulario. Contem um PONTO, por isso o seletor e por atributo
    (`[id='...']`), nao `#id` (CSS exigiria escapar o ponto).

    O id do DIALOGO em si (`components_LookupDialog_7` no HTML capturado) e
    NUMERADO por ordem de criacao na pagina — muda a cada abertura e por isso NAO
    pode ser usado como seletor. O botao Cancelar e a unica peca estavel.
    """
    return f"[id='{campo.sufixo}.lookup._cancelbutton']"


def id_lookup_dialog_usar_selecionado(campo: Campo) -> str:
    """Botao OK ('usar selecionado') do mesmo dialogo modal — ver
    `id_lookup_dialog_cancelar` para o porque de nao levar prefixo."""
    return f"[id='{campo.sufixo}.lookup._lookupUseSelectedButton']"


def id_lookup_dialog_resultados_contagem() -> str:
    """Id do contador de resultados dentro do dialogo modal ('resultsCount').

    NAO leva o sufixo do campo — e um unico elemento fixo do widget de
    dialogo, confirmado em tela viva (2026-08-13): mostra '0' quando a busca
    por codigo exato (ex.: tombo '*332255') nao acha nada, e '1' quando acha
    um so resultado exato (nesse caso o widget normalmente resolve sozinho,
    sem nem abrir o dialogo — ver `_preencher_item_b` no flow).
    """
    return "resultsCount"


def id_campo_hora(prefixo: str, campo: Campo) -> str:
    """Segunda metade de um campo DATA_HORA (o input de hora)."""
    if campo.tipo != DATA_HORA:
        raise ValueError(f"{campo.chave} nao e um campo de data/hora")
    return f"#{campo.sufixo}Time"
