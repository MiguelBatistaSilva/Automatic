"""
pages/atendimento.py — Tela da aba "Iniciar Atendimento".

Só a view: formulário de agendamento e tabela da agenda. O back-end está em
`state/atendimento_state.py`; a agenda é a mesma do Assistente.
"""

import reflex as rx

from services.agente.agendados import AGUARDANDO, CANCELADO, CONCLUIDO, ERRO, EXECUTANDO, PENDENTE, _TOLERANCIA_MIN
from state.atendimento_state import AtendimentoState
from components.layout import page_layout
from components.botoes import botao_primario, botao_secundario, botao_icone


def _badge_status(status: rx.Var) -> rx.Component:
    """Status como badge colorido. Um rx.match por estado porque o `color_scheme`
    do badge e um literal — nao aceita Var."""
    return rx.match(
        status,
        (EXECUTANDO, rx.badge("Executando", color_scheme="cyan")),
        (CONCLUIDO, rx.badge("Concluído", color_scheme="green")),
        (ERRO, rx.badge("Erro", color_scheme="red")),
        (CANCELADO, rx.badge("Cancelado", color_scheme="amber")),
        (AGUARDANDO, rx.badge("Aguardando", color_scheme="orange")),
        rx.badge("Pendente", color_scheme="gray"),  # PENDENTE = caso padrão
    )


def _linha_agenda(item: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(item.chamado),
        rx.table.cell(rx.cond(item.quando_label != "", item.quando_label, "—")),
        rx.table.cell(_badge_status(item.status)),
        rx.table.cell(item.detalhe),
        rx.table.cell(
            rx.cond(
                item.status != EXECUTANDO,
                botao_icone(
                    "x",
                    on_click=AtendimentoState.remover(item.id),
                    title="Excluir da agenda",
                ),
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
                rx.table.column_header_cell("Detalhe"),
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
            "Agende chamados em Atendimento Programado; na hora marcada, o atendimento é "
            f"iniciado sozinho, com o app ou o bot aberto. Passados {_TOLERANCIA_MIN} min da hora "
            "sem nenhum deles aberto, não inicia mais.",
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
                botao_primario("Agendar", on_click=AtendimentoState.adicionar,
                               margin_top="0.5em"),
                spacing="1",
                align_items="stretch",
                width="260px",
            ),
            rx.vstack(
                rx.hstack(
                    rx.text("Agenda", weight="bold"),
                    rx.hstack(
                        rx.button(
                            rx.icon("shield", size=16),
                            rx.cond(AtendimentoState.sentinela_ligado,
                                    "Sentry Mode: ligado", "Sentry Mode"),
                            on_click=AtendimentoState.alternar_sentinela,
                            variant=rx.cond(AtendimentoState.sentinela_ligado, "solid", "soft"),
                            color_scheme=rx.cond(AtendimentoState.sentinela_ligado, "green", "gray"),
                            cursor="pointer",
                            title=AtendimentoState.sentinela_info,
                        ),
                        botao_secundario("Atualizar", on_click=AtendimentoState.carregar),
                        spacing="2",
                    ),
                    justify="between",
                    align="center",
                    width="100%",
                ),
                _tabela_agenda(),
                spacing="2",
                align_items="stretch",
                flex="1",
            ),
            spacing="5",
            width="100%",
            align_items="start",
        ),
        spacing="4",
        width="100%",
    )
    return page_layout(conteudo)
