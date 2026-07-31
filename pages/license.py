"""
pages/license.py — Tela da aba Licenças.

Só a view. O back-end (login em laço deixando o Chrome aberto) está em
`state/license_state.py`.
"""

import reflex as rx

from state.license_state import LicenseState
from components.log_console import log_console
from components.layout import page_layout
from components.botoes import botao_primario


def license_page() -> rx.Component:
    conteudo = rx.vstack(
        rx.heading("Licenças", size="6"),
        rx.text(
            "Faz login no Assyst quando todas as licenças estão em uso e deixa o Chrome aberto "
            "para uso manual.",
            color="#6B7280",
        ),
        botao_primario(
            "Abrir sessão",
            on_click=LicenseState.abrir_sessao,
            disabled=LicenseState.rodando,
        ),
        log_console(LicenseState.logs),
        spacing="4",
        width="100%",
    )
    return page_layout(conteudo)
