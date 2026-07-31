"""
pages/sla.py — Tela da aba "Análise de SLA".

Só a view: formulário, tabela de resultados e console de logs. O back-end (fluxo,
cálculo e a dataclass `SLAResultado`) está em `state/sla_state.py`.
"""

import reflex as rx

from state.sla_state import SLAState
from components.log_console import log_console
from components.layout import page_layout
from components.form import coluna, duas_colunas, ALTURA_TEXTAREA
from components.botoes import botao_primario


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
                rx.text("Fila", weight="bold"),
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
