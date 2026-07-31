"""
components/dialog_credenciais.py — Credenciais do CATI/Assyst (keyring), como POP-UP.

Era uma página/rota (`/credenciais`); virou um `rx.dialog` aberto pelo menu de opções
da sidebar — como no antigo `ui/dialog_credenciais.py` do Qt. Só a view; o
`CredenciaisState` (e o acesso ao keyring) está em `state/credenciais_state.py`.

O diálogo é CONTROLADO (`aberto`): quem abre é o item do menu, que chama `abrir`
(carrega o que está salvo antes de mostrar).
"""

import reflex as rx

from state.credenciais_state import CredenciaisState
from components.botoes import botao_primario, botao_secundario, botao_perigo


def credenciais_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Credenciais"),
            rx.dialog.description(
                "Credenciais do CATI/Assyst, usadas por todas as automações. A senha "
                "é guardada no Cofre de Credenciais do Windows, não em arquivo.",
                color="#6B7280",
                size="2",
            ),
            rx.vstack(
                rx.text("Matrícula", weight="bold", size="2"),
                rx.input(placeholder="400123", value=CredenciaisState.matricula,
                         on_change=CredenciaisState.set_matricula, width="100%"),
                rx.text("Senha", weight="bold", size="2", margin_top="0.5em"),
                rx.input(
                    placeholder="••••••",
                    type=rx.cond(CredenciaisState.mostrar_senha, "text", "password"),
                    value=CredenciaisState.senha,
                    on_change=CredenciaisState.set_senha,
                    width="100%",
                ),
                rx.checkbox("Mostrar senha", checked=CredenciaisState.mostrar_senha,
                            on_change=CredenciaisState.toggle_mostrar, size="1"),
                spacing="1",
                align_items="start",
                width="100%",
                margin_top="1em",
            ),
            rx.text(CredenciaisState.status, color=CredenciaisState.status_cor,
                    size="2", margin_top="0.75em"),
            rx.hstack(
                botao_perigo("Apagar", on_click=CredenciaisState.apagar,
                             disabled=~CredenciaisState.tem_salvas),
                rx.spacer(),
                rx.dialog.close(botao_secundario("Fechar")),
                botao_primario("Salvar", on_click=CredenciaisState.salvar),
                spacing="3",
                width="100%",
                margin_top="1.25em",
                align="center",
            ),
            max_width="420px",
        ),
        open=CredenciaisState.aberto,
        on_open_change=CredenciaisState.set_aberto,
    )
