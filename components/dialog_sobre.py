"""
components/dialog_sobre.py — "Sobre", como POP-UP.

Era uma página/rota (`/sobre`); virou um `rx.dialog` aberto pelo menu de opções da
sidebar.

A checagem de atualização foi RETIRADA em 2026-07-27: a distribuição passou a ser
manual (baixar o zip do GitHub e rodar o `iniciar_automatic.bat`), então não há
mais versão instalada para comparar. Saíram junto o `version.py`, o `version.json`
e o `services/update_check.py`.
"""

import reflex as rx

from components.botoes import botao_secundario

_URL_SOBRE = "https://recondite-frog-e5d.notion.site/Bem-vindo-2e6e32b25a248027b36ef626bf484553"


class SobreState(rx.State):
    aberto: bool = False

    @rx.event
    def abrir(self):
        self.aberto = True

    @rx.event
    def set_aberto(self, v: bool):
        self.aberto = v


def sobre_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Sobre"),
            rx.vstack(
                rx.text("Automatic", weight="bold", size="4"),
                rx.link("📖  Documentação (Notion)", href=_URL_SOBRE,
                        is_external=True, size="2"),
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
