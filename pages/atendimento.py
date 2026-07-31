"""
pages/atendimento.py — Tela da aba "Iniciar Atendimento".

Só a view: formulário de agendamento, tabela da agenda e console de logs. O
back-end (o laço que substitui o QTimer, a dataclass `AgendaItem` e os estados)
está em `state/atendimento_state.py`.
"""

import reflex as rx

from state.atendimento_state import (
    AtendimentoState, STATUS_EXECUTANDO, STATUS_CONCLUIDO, STATUS_ERRO,
)
from components.log_console import log_console
from components.layout import page_layout
from components.botoes import botao_primario, botao_secundario, botao_icone


def _badge_status(status: rx.Var) -> rx.Component:
    """Status como badge colorido. Um rx.match por estado porque o `color_scheme`
    do badge e um literal — nao aceita Var."""
    return rx.match(
        status,
        (STATUS_EXECUTANDO, rx.badge("Executando", color_scheme="cyan")),
        (STATUS_CONCLUIDO, rx.badge("Concluído", color_scheme="green")),
        (STATUS_ERRO, rx.badge("Erro", color_scheme="red")),
        rx.badge("Pendente", color_scheme="gray"),  # STATUS_PENDENTE = caso padrão
    )


def _linha_agenda(item: rx.Var, idx: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(item.chamado),
        rx.table.cell(item.quando_label),
        rx.table.cell(_badge_status(item.status)),
        rx.table.cell(
            botao_icone(
                "x",
                on_click=AtendimentoState.remover(idx),
                title="Remover da agenda",
            ),
        ),
    )


def _tabela_agenda() -> rx.Component:
    return rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("Chamado"),
                rx.table.column_header_cell("Agendado para"),
                rx.table.column_header_cell("Status"),
                rx.table.column_header_cell(""),
            ),
        ),
        rx.table.body(rx.foreach(AtendimentoState.agenda, _linha_agenda)),
        width="100%",
        variant="surface",
    )


def atendimento_page() -> rx.Component:
    conteudo = rx.vstack(
        rx.heading("Iniciar Atendimento", size="6"),
        rx.text(
            "Agende chamados em Atendimento Programado; quando bate a hora, o fluxo inicia o atendimento.",
            color="#6B7280",
        ),
        rx.hstack(
            rx.vstack(
                rx.text("Chamado", weight="bold"),
                rx.input(
                    placeholder="S2397518",
                    value=AtendimentoState.novo_chamado,
                    on_change=AtendimentoState.set_novo_chamado,
                ),
                rx.text("Iniciar em (dia e hora)", weight="bold", margin_top="0.5em"),
                rx.input(
                    type="datetime-local",
                    value=AtendimentoState.data_hora,
                    on_change=AtendimentoState.set_data_hora,
                ),
                botao_secundario("Agendar", on_click=AtendimentoState.adicionar,
                                 margin_top="0.5em"),
                rx.cond(
                    AtendimentoState.armado,
                    botao_primario("Pausar agendamento", on_click=AtendimentoState.desarmar,
                                   color_scheme="amber", margin_top="0.5em"),
                    botao_primario("Ativar agendamento", on_click=AtendimentoState.armar,
                                   margin_top="0.5em"),
                ),
                spacing="1",
                align_items="stretch",
                width="260px",
            ),
            rx.vstack(
                rx.text("Agenda", weight="bold"),
                _tabela_agenda(),
                spacing="2",
                align_items="stretch",
                flex="1",
            ),
            spacing="5",
            width="100%",
            align_items="start",
        ),
        rx.heading("Registro de Execução", size="4", margin_top="0.5em"),
        log_console(AtendimentoState.logs),
        spacing="4",
        width="100%",
    )
    return page_layout(conteudo)
