"""
pages/sla.py — Tela da aba "Análise de SLA".

Só a view: formulário, tabela de resultados e console de logs. O back-end (fluxo,
cálculo e a dataclass `SLAResultado`) está em `state/sla_state.py`.
"""

import reflex as rx

from state.sla_state import SLAState, FILAS_INFO, EXPEDIENTE
from components.log_console import log_console
from components.layout import page_layout
from components.form import coluna, duas_colunas, ALTURA_TEXTAREA
from components.botoes import botao_primario


def _linha_fila(info) -> rx.Component:
    """Uma fila no quadro de regras. Montada em Python puro (build-time), nao com
    `rx.foreach`: `FILAS_INFO` vem do `sla_engine` e nao muda em execucao."""
    return rx.table.row(
        rx.table.cell(info.nome),
        rx.table.cell(info.prazo, weight="bold"),
        rx.table.cell(
            rx.badge(
                info.fim_de_semana,
                color_scheme="blue" if info.corre_no_fds else "gray",
                variant="soft",
            ),
        ),
    )


def _regras_das_filas() -> rx.Component:
    """Pop-up com o resumo das filas: prazo e o que acontece no fim de semana.

    Pop-up e nao tooltip porque sao 8 linhas com colunas — tooltip e para uma frase.
    Fica ao lado do rotulo 'Fila', que e onde a duvida aparece.
    """
    return rx.popover.root(
        rx.popover.trigger(
            rx.button(
                rx.icon("info", size=14),
                size="1",
                variant="ghost",
                color_scheme="gray",
                cursor="pointer",
                # So o icone (decisao do usuario). O `title` e a dica nativa do
                # navegador: aparece no hover, sem ocupar espaco na tela.
                title="Regras das filas",
            ),
        ),
        rx.popover.content(
            rx.vstack(
                rx.text("Como o tempo é contado", weight="bold", size="2"),
                rx.text(
                    f"O relógio corre das {EXPEDIENTE}, todos os dias. Fora desse "
                    "horário ele congela para todas as filas.",
                    size="1",
                    color=rx.color("gray", 11),
                ),
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("Fila"),
                            rx.table.column_header_cell("Prazo"),
                            rx.table.column_header_cell("Fim de semana"),
                        ),
                    ),
                    rx.table.body(*[_linha_fila(i) for i in FILAS_INFO]),
                    size="1",
                    variant="surface",
                    width="100%",
                ),
                spacing="2",
                align_items="stretch",
            ),
            width="480px",
            max_width="90vw",
        ),
    )


def _linha_resultado(r: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(r.numero, font_weight="bold"),
        rx.table.cell(r.inicio),
        rx.table.cell(r.tempo),
        rx.table.cell(
            r.status,
            color=rx.cond(r.erro, "#DC2626", "#16A34A"),
            font_weight="bold",
        ),
        rx.table.cell(r.acoes),
    )


def _tabela() -> rx.Component:
    return rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("Chamado"),
                rx.table.column_header_cell("Início"),
                rx.table.column_header_cell("Tempo de SLA"),
                rx.table.column_header_cell("Status"),
                rx.table.column_header_cell("Ações"),
            ),
        ),
        rx.table.body(rx.foreach(SLAState.resultados, _linha_resultado)),
        width="100%",
        variant="surface",
    )


def sla_page() -> rx.Component:
    conteudo = rx.vstack(
        rx.heading("Análise de SLA", size="6"),
        rx.text(
            "Calcula o tempo líquido de SLA de cada chamado a partir do histórico de ações.",
            color="#6B7280",
        ),
        # Mesmas colunas do Desmembramento: metade/metade, campo grande à direita.
        duas_colunas(
            coluna(
                rx.hstack(
                    rx.text("Fila", weight="bold"),
                    _regras_das_filas(),
                    align="center",
                    spacing="2",
                ),
                rx.select(
                    SLAState.filas,
                    value=SLAState.fila,
                    on_change=SLAState.set_fila,
                    width="100%",
                ),
            ),
            coluna(
                rx.text("Chamados (um por linha)", weight="bold"),
                rx.text_area(
                    placeholder="S2123456\nS2123457\nS2123458",
                    value=SLAState.chamados_texto,
                    on_change=SLAState.set_chamados_texto,
                    height=ALTURA_TEXTAREA,
                    width="100%",
                    font_family="monospace",
                ),
            ),
        ),
        botao_primario(
            "Analisar SLA",
            on_click=SLAState.analisar,
            disabled=SLAState.rodando,
        ),
        rx.heading("Resultados", size="4", margin_top="0.5em"),
        _tabela(),
        rx.heading("Registro de Execução", size="4", margin_top="0.5em"),
        log_console(SLAState.logs),
        spacing="4",
        width="100%",
    )
    return page_layout(conteudo)
