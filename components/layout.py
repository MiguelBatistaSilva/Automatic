"""
components/layout.py — Casca comum das páginas (sidebar + conteúdo).

Cada page function chama `page_layout(<conteudo>)`. A página ativa é destacada
reativamente pela própria sidebar (via router), então não há mais parâmetro `active`.
"""

import reflex as rx

from components.sidebar import sidebar


def page_layout(content: rx.Component) -> rx.Component:
    return rx.hstack(
        sidebar(),
        rx.box(
            content,
            flex="1",
            width="100%",
            min_width="0",
            height="100vh",
            overflow_y="auto",
            background_color=rx.color("gray", 1),
            padding="32px 40px",
        ),
        spacing="0",
        align="start",
        width="100%",
        min_height="100vh",
    )
