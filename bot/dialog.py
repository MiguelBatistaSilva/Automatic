"""
bot/dialog.py — Pop-up "Telegram" (menu de opções da sidebar).

Só o token do bot (@BotFather). A whitelist de chat_ids (aba "Usuários
Autorizados") morava aqui e foi para a página Configurações em 2026-09-09 —
as duas são config exclusiva do bot, junto faz mais sentido do que uma no
pop-up e outra numa página (ver `pages/configuracoes.py`). Só a view; o
`TelegramState` (e o acesso ao keyring do bot) está em `bot/state.py`.

O diálogo é CONTROLADO (`aberto`): quem abre é o item do menu, que chama
`abrir` (carrega o que está salvo antes de mostrar).
"""

import reflex as rx

from bot.state import TelegramState
from components.botoes import botao_secundario


def telegram_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Telegram"),
            rx.dialog.description(
                "Adicione o token do bot do Telegram aqui.",
                color="#6B7280",
                size="2",
            ),
            rx.vstack(
                rx.text("Token do bot", weight="bold", size="2", margin_top="1em"),
                rx.input(
                    placeholder="dado pelo @BotFather",
                    type=rx.cond(TelegramState.mostrar_token, "text", "password"),
                    value=TelegramState.token,
                    on_change=TelegramState.set_token,
                    width="100%",
                ),
                rx.hstack(
                    rx.checkbox(
                        "Mostrar",
                        checked=TelegramState.mostrar_token,
                        on_change=TelegramState.toggle_mostrar_token,
                        size="1",
                    ),
                    rx.spacer(),
                    botao_secundario("Salvar token", on_click=TelegramState.salvar_token),
                    width="100%",
                    align="center",
                    margin_top="0.5em",
                ),
                spacing="1",
                align_items="start",
                width="100%",
            ),
            rx.text(
                TelegramState.status,
                color=TelegramState.status_cor,
                size="2",
                margin_top="0.75em",
            ),
            rx.hstack(
                rx.spacer(),
                rx.dialog.close(botao_secundario("Fechar")),
                width="100%",
                margin_top="1.25em",
                align="center",
            ),
            max_width="440px",
        ),
        open=TelegramState.aberto,
        on_open_change=TelegramState.set_aberto,
    )
