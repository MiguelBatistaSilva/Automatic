"""
components/dialog_sobre.py — "Sobre", como POP-UP.

Era uma página/rota (`/sobre`); virou um `rx.dialog` aberto pelo menu de opções da
sidebar. Só a view — o `SobreState` está em `state/sobre_state.py`.
"""

import reflex as rx

from state.sobre_state import SobreState
from components.botoes import botao_primario, botao_secundario

_URL_DOCUMENTACAO = "https://recondite-frog-e5d.notion.site/Bem-vindo-2e6e32b25a248027b36ef626bf484553"

_DESCRICAO = (
    "Ferramenta de automação para o Assyst/TJCE. Reúne módulos, como: desmembramento de chamados, início de atendimentos "
    "agendados, análise de SLA e gerenciamento das Bases de Conhecimento.",
)


def sobre_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Sobre"),
            rx.vstack(
                rx.text("Automatic", weight="regular", size="4"),
                *[rx.text(p, size="2") for p in _DESCRICAO],
                rx.tooltip(
                    rx.link(
                        botao_primario(rx.icon("arrow-up-right", size=16)),
                        href=_URL_DOCUMENTACAO,
                        is_external=True,
                        margin_top="0.5em",
                    ),
                    content="Link",
                ),
                spacing="2",
                align_items="start",
                width="100%",
                margin_top="0.75em",
            ),
            rx.hstack(
                rx.spacer(),
                rx.dialog.close(botao_secundario("Fechar")),
                width="100%",
                margin_top="1.25em",
            ),
            max_width="420px",
        ),
        open=SobreState.aberto,
        on_open_change=SobreState.set_aberto,
    )
