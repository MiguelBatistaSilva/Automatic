"""
bot/dialog.py — Pop-up "Telegram" (menu de opções da sidebar).

Reúne token do bot, credencial única do bot para o Assyst e a whitelist de
chat_ids — as três coisas que `cadastrar.py` fazia por terminal. Só a view;
o `TelegramState` (e o acesso ao keyring/JSON do bot) está em `bot/state.py`.

O diálogo é CONTROLADO (`aberto`): quem abre é o item do menu, que chama
`abrir` (carrega o que está salvo antes de mostrar).
"""

import reflex as rx

from bot.state import TelegramState
from components.botoes import botao_secundario, botao_tabela


def _linha_usuario(item: rx.Var[tuple[str, str]]) -> rx.Component:
    chat_id, nome = item[0], item[1]
    return rx.hstack(
        rx.text(nome, size="2", weight="medium"),
        rx.text(chat_id, size="1", color="#6B7280"),
        rx.spacer(),
        botao_tabela(rx.icon("x", size=13), on_click=TelegramState.remover_usuario(chat_id)),
        width="100%",
        align="center",
        spacing="2",
    )


def telegram_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Telegram"),
            rx.dialog.description(
                "Configuração do bot do Telegram — token e quem pode falar com "
                "ele. Cada pessoa liberada cadastra a PRÓPRIA credencial do "
                "Assyst direto no bot, com /credencial — não é feito aqui.",
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
                ),
                rx.divider(margin_y="0.5em"),
                rx.text("Quem pode falar com o bot", weight="bold", size="2"),
                rx.text(
                    "Depois de liberado(a) aqui, a pessoa manda /credencial "
                    "pro próprio bot pra cadastrar a matrícula/senha dela.",
                    size="1",
                    color="#6B7280",
                ),
                rx.vstack(
                    rx.foreach(TelegramState.usuarios, _linha_usuario),
                    rx.cond(
                        TelegramState.usuarios.length() == 0,
                        rx.text("Ninguém liberado ainda.", size="1", color="#6B7280"),
                    ),
                    width="100%",
                    spacing="2",
                    margin_top="0.5em",
                ),
                rx.hstack(
                    rx.input(
                        placeholder="chat_id",
                        value=TelegramState.novo_chat_id,
                        on_change=TelegramState.set_novo_chat_id,
                        width="45%",
                    ),
                    rx.input(
                        placeholder="Nome/apelido",
                        value=TelegramState.novo_nome,
                        on_change=TelegramState.set_novo_nome,
                        width="55%",
                    ),
                    width="100%",
                    margin_top="0.5em",
                ),
                botao_secundario(
                    "Liberar",
                    on_click=TelegramState.adicionar_usuario,
                    width="100%",
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
