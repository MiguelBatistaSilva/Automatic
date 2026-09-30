"""
pages/meus_fluxos.py — Tela "Meus fluxos": histórico das rodadas da matrícula logada.

Só a view. Cada rodada é uma linha clicável; abrir mostra os chamados dela.
O back-end está em `state/meus_fluxos_state.py`.
"""

import reflex as rx

from state.meus_fluxos_state import (
    MeusFluxosState, FILTROS_FLUXO, FILTROS_STATUS,
)
from components.layout import page_layout
from components.botoes import botao_secundario


def _linha_detalhe(l: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(l.linha),
        rx.table.cell(rx.cond(l.referencia != "", l.referencia, "—")),
        rx.table.cell(rx.cond(l.gerado != "", l.gerado, "—"), font_weight="bold"),
        rx.table.cell(rx.badge(l.status, color_scheme=l.cor, variant="soft")),
    )


def _detalhe(r: rx.Var) -> rx.Component:
    return rx.box(
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Linha"),
                    rx.table.column_header_cell("Referência"),
                    rx.table.column_header_cell("Chamado gerado"),
                    rx.table.column_header_cell("Status"),
                ),
            ),
            rx.table.body(rx.foreach(r.linhas, _linha_detalhe)),
            size="1",
            width="100%",
        ),
        padding="0 12px 12px",
        width="100%",
        overflow_x="auto",
    )


def _rodada(r: rx.Var) -> rx.Component:
    aberta = MeusFluxosState.aberta == r.id
    return rx.box(
        rx.hstack(
            rx.icon(
                rx.cond(aberta, "chevron-down", "chevron-right"),
                size=16, color=rx.color("gray", 10), flex_shrink="0",
            ),
            rx.vstack(
                rx.text(r.titulo, weight="bold"),
                rx.text(
                    r.fluxo, " · ", r.origem, " · ", r.quando,
                    size="1", color=rx.color("gray", 11),
                ),
                spacing="0",
                min_width="0",
            ),
            rx.spacer(),
            rx.text(r.progresso, size="2", color=rx.color("gray", 11)),
            rx.badge(r.status, color_scheme=r.cor, variant="soft"),
            align="center",
            spacing="3",
            padding="10px 12px",
            width="100%",
            cursor="pointer",
            on_click=MeusFluxosState.alternar(r.id),
        ),
        rx.cond(aberta, _detalhe(r), rx.fragment()),
        border=f"1px solid {rx.color('gray', 6)}",
        border_radius="8px",
        background=rx.color("gray", 1),
        width="100%",
    )


def _filtros() -> rx.Component:
    return rx.hstack(
        rx.select(FILTROS_FLUXO, value=MeusFluxosState.filtro_fluxo,
                  on_change=MeusFluxosState.set_filtro_fluxo),
        rx.select(FILTROS_STATUS, value=MeusFluxosState.filtro_status,
                  on_change=MeusFluxosState.set_filtro_status),
        rx.spacer(),
        botao_secundario(rx.icon("refresh-cw", size=14), "Atualizar",
                         on_click=MeusFluxosState.on_load),
        width="100%",
        align="center",
        flex_wrap="wrap",
    )


def meus_fluxos_page() -> rx.Component:
    conteudo = rx.vstack(
        rx.heading("Meus fluxos", size="6"),
        rx.text(
            "Os fluxos que você rodou, pelo app ou pelo bot, e os chamados que cada um gerou.",
            color="#6B7280",
        ),
        rx.cond(
            MeusFluxosState.matricula == "",
            rx.callout(
                "Cadastre suas credenciais (Opções → Credenciais) para ver o seu histórico.",
                icon="info",
                width="100%",
            ),
            rx.vstack(
                _filtros(),
                rx.cond(
                    MeusFluxosState.filtradas.length() > 0,
                    rx.vstack(
                        rx.foreach(MeusFluxosState.filtradas, _rodada),
                        spacing="2",
                        width="100%",
                    ),
                    rx.text("Nenhum fluxo encontrado.", color=rx.color("gray", 11)),
                ),
                spacing="3",
                width="100%",
            ),
        ),
        spacing="4",
        width="100%",
    )
    return page_layout(conteudo)
