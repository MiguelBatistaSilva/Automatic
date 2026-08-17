"""
pages/requisicao.py — Tela da aba "Requisição de Serviço".

Só a view: a caixa da entrada com um exemplo abaixo, a tabela de resultados e o
console de logs. O back-end está em `state/requisicao_state.py`.

Tanto o placeholder (rótulos na ordem) quanto o exemplo saem de `ORDEM_COLUNAS`, e
não escritos à mão: se a ordem mudar no catálogo, a tela acompanha em vez de mentir.
"""

import reflex as rx

from state.requisicao_state import RequisicaoState, EXEMPLO_ORDEM, EXEMPLOS_PREENCHIDOS
from components.log_console import log_console
from components.layout import page_layout
from components.form import coluna, ALTURA_TEXTAREA
from components.botoes import botao_primario


def _exemplos() -> rx.Component:
    """UM quadro de exemplo, com as linhas (varios cenarios) empilhadas dentro —
    cada linha ilustra um formato diferente de Item B (o campo que mais confunde:
    tombo vs. valor comum). `EXEMPLOS_PREENCHIDOS` vem PRONTA (Python puro, nao
    Var do Reflex), entao e so um loop normal, nao `rx.foreach`.

    So os VALORES em cada linha (decisao do usuario). Os nomes dos campos ficam no
    placeholder da caixa. `white_space="pre"` para cada linha NAO quebrar: em duas
    linhas ela pareceria duas requisições — por isso o quadro rola na horizontal.
    """
    return rx.vstack(
        rx.text("Exemplo de preenchimento:", size="1", color=rx.color("gray", 11)),
        rx.box(
            rx.vstack(
                *[
                    rx.text(
                        linha,
                        size="1",
                        font_family="monospace",
                        white_space="pre",
                        color=rx.color("gray", 12),
                    )
                    for _, linha in EXEMPLOS_PREENCHIDOS
                ],
                spacing="2",
                align_items="stretch",
            ),
            width="100%",
            overflow_x="auto",
            padding="0.5em 0.7em",
            border=f"1px solid {rx.color('gray', 6)}",
            border_radius="6px",
            background=rx.color("gray", 2),
        ),
        spacing="1",
        width="100%",
        align_items="stretch",
    )


def _campo_entrada() -> rx.Component:
    # `coluna()` nao declara largura, e o vstack da pagina usa align="start" — o
    # que faz filho sem largura ENCOLHER ate o conteudo. As outras paginas nao
    # tropecam nisso porque passam os campos por `duas_colunas()`, que ja e 100%.
    # Aqui o campo vai sozinho na linha, entao a largura precisa vir daqui.
    return rx.box(_conteudo_entrada(), width="100%")


def _conteudo_entrada() -> rx.Component:
    return coluna(
        rx.text("Requisições (uma por linha)", weight="bold"),
        rx.text_area(
            placeholder=EXEMPLO_ORDEM,
            value=RequisicaoState.entrada_texto,
            on_change=RequisicaoState.set_entrada_texto,
            height=ALTURA_TEXTAREA,
            width="100%",
            font_family="monospace",
        ),
        _exemplos(),
    )


def _linha_resultado(r: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(r.linha),
        rx.table.cell(r.usuario),
        rx.table.cell(r.numero, font_weight="bold"),
        rx.table.cell(
            r.status,
            color=rx.cond(r.erro, "#DC2626", "#16A34A"),
            font_weight="bold",
        ),
    )


def _tabela() -> rx.Component:
    return rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("Linha"),
                rx.table.column_header_cell("Usuário afetado"),
                rx.table.column_header_cell("Chamado criado"),
                rx.table.column_header_cell("Status"),
            ),
        ),
        rx.table.body(rx.foreach(RequisicaoState.resultados, _linha_resultado)),
        width="100%",
        variant="surface",
    )


def requisicao_page() -> rx.Component:
    conteudo = rx.vstack(
        rx.heading("Requisição de Serviço", size="6"),
        rx.text(
            "Abre chamados novos no Assyst a partir de uma lista — um por linha.",
            color="#6B7280",
        ),
        _campo_entrada(),
        botao_primario(
            "Criar requisições",
            on_click=RequisicaoState.iniciar,
            disabled=RequisicaoState.rodando,
        ),
        rx.heading("Resultados", size="4", margin_top="0.5em"),
        _tabela(),
        rx.heading("Registro de Execução", size="4", margin_top="0.5em"),
        log_console(RequisicaoState.logs),
        spacing="4",
        width="100%",
    )
    return page_layout(conteudo)
