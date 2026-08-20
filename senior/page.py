"""
senior/page.py — Tela "Ponto" (Senior HCM).

SEM entrada em components/sidebar.py NAV_ITEMS de propósito: automação à parte,
site e credencial diferentes do Assyst. Só acessível digitando /ponto no
navegador. O back-end está em senior/state.py.
"""

import reflex as rx

from senior.state import (
    PontoState, STATUS_EXECUTANDO, STATUS_CONCLUIDO, STATUS_ERRO, STATUS_EXPIRADO,
)
from components.log_console import log_console
from components.layout import page_layout
from components.botoes import botao_primario, botao_secundario


def _badge_status(status: rx.Var) -> rx.Component:
    return rx.match(
        status,
        (STATUS_EXECUTANDO, rx.badge("Executando", color_scheme="cyan")),
        (STATUS_CONCLUIDO, rx.badge("Concluído", color_scheme="green")),
        (STATUS_ERRO, rx.badge("Erro", color_scheme="red")),
        (STATUS_EXPIRADO, rx.badge("Expirado", color_scheme="amber")),
        rx.badge("Pendente", color_scheme="gray"),  # STATUS_PENDENTE = caso padrão
    )


def _linha_agenda(item: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(item.label, font_weight="bold"),
        rx.table.cell(_badge_status(item.status)),
    )


def _tabela_agenda() -> rx.Component:
    return rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("Horário"),
                rx.table.column_header_cell("Status"),
            ),
        ),
        rx.table.body(rx.foreach(PontoState.agenda, _linha_agenda)),
        width="100%",
        variant="surface",
    )


def _credenciais() -> rx.Component:
    return rx.vstack(
        rx.text("Credencial (Senior HCM)", weight="bold", size="2"),
        rx.text(
            "Guardada no Cofre de Credenciais do Windows, num cofre separado do "
            "usado pelo Assyst.",
            size="1",
            color="#6B7280",
        ),
        rx.input(
            placeholder="usuario@lanlink.com.br",
            value=PontoState.usuario,
            on_change=PontoState.set_usuario,
            width="100%",
            margin_top="0.5em",
        ),
        rx.input(
            placeholder="••••••",
            type=rx.cond(PontoState.mostrar_senha, "text", "password"),
            value=PontoState.senha,
            on_change=PontoState.set_senha,
            width="100%",
        ),
        rx.hstack(
            rx.checkbox(
                "Mostrar",
                checked=PontoState.mostrar_senha,
                on_change=PontoState.toggle_mostrar_senha,
                size="1",
            ),
            rx.spacer(),
            botao_secundario("Salvar credencial", on_click=PontoState.salvar_credencial),
            width="100%",
            align="center",
        ),
        rx.text(PontoState.cred_status, color=PontoState.cred_status_cor, size="2"),
        spacing="1",
        align_items="stretch",
        width="260px",
    )


def ponto_page() -> rx.Component:
    conteudo = rx.vstack(
        rx.heading("Ponto — Senior HCM", size="6"),
        rx.text(
            "",
            color="#6B7280",
        ),
        rx.hstack(
            _credenciais(),
            rx.vstack(
                rx.text("Horários de hoje (HH:MM)", weight="bold"),
                rx.hstack(
                    rx.input(placeholder="08:00", value=PontoState.horario1,
                              on_change=PontoState.set_horario1, width="90px"),
                    rx.input(placeholder="12:00", value=PontoState.horario2,
                              on_change=PontoState.set_horario2, width="90px"),
                    rx.input(placeholder="13:00", value=PontoState.horario3,
                              on_change=PontoState.set_horario3, width="90px"),
                    rx.input(placeholder="18:00", value=PontoState.horario4,
                              on_change=PontoState.set_horario4, width="90px"),
                    spacing="2",
                ),
                rx.checkbox(
                    "Mostrar navegador",
                    checked=PontoState.mostrar_navegador,
                    on_change=PontoState.toggle_mostrar_navegador,
                    size="1",
                    margin_top="0.25em",
                ),
                rx.hstack(
                    rx.cond(
                        PontoState.armado,
                        botao_primario("Pausar agendamento", on_click=PontoState.desarmar,
                                       color_scheme="amber", disabled=PontoState.rodando),
                        botao_primario("Ativar agendamento", on_click=PontoState.armar,
                                       disabled=PontoState.rodando),
                    ),
                    botao_secundario("Simular agora", on_click=PontoState.testar(False),
                                      disabled=PontoState.rodando | PontoState.armado),
                    botao_secundario("Bater agora", on_click=PontoState.testar(True),
                                      disabled=PontoState.rodando | PontoState.armado),
                    spacing="2",
                    margin_top="0.5em",
                ),
                rx.cond(
                    PontoState.agenda,
                    _tabela_agenda(),
                ),
                spacing="2",
                align_items="stretch",
                flex="1",
            ),
            spacing="5",
            width="100%",
            align_items="start",
        ),
        rx.heading("Registro de Execução", size="4", margin_top="0.5em"),
        log_console(PontoState.logs),
        spacing="4",
        width="100%",
    )
    return page_layout(conteudo)
