"""Menu do rodapé da sidebar — um dropdown com opções secundárias.

Espelha o `user_menu` do projeto Asset Management (mesmo padrão de dropdown nativo),
mas aqui não há usuário/login: o menu abre Credenciais e Sobre em POP-UP (diálogos,
não rotas) e alterna o tema claro/escuro. Adapta-se ao estado colapsado/expandido
da sidebar.

Os diálogos são montados AQUI, irmãos do dropdown (nunca dentro do
`dropdown_menu.content`: ao fechar, o menu desmontaria o diálogo junto). O item do
menu só liga o `aberto` do state correspondente. O `modal=False` no dropdown evita
o conflito de foco/pointer-events do Radix ao abrir um diálogo a partir do menu.
"""

import reflex as rx

from state.sidebar_state import SidebarState
from state.credenciais_state import CredenciaisState
from state.sobre_state import SobreState
from components.dialog_credenciais import credenciais_dialog
from components.dialog_sobre import sobre_dialog


def _trigger() -> rx.Component:
    """Botão que abre o menu. Expandido mostra o rótulo; contraído, só o ícone centrado."""
    return rx.button(
        rx.icon("settings", size=16, flex_shrink="0"),
        rx.cond(
            ~SidebarState.collapsed,
            rx.fragment(
                rx.text(
                    "Opções",
                    size="1",
                    font_size="13px",  # acompanha os itens de navegação
                    white_space="nowrap",
                    overflow="hidden",
                    flex="1",
                    text_align="left",
                ),
                rx.icon("chevrons-up-down", size=13, color=rx.color("gray", 10)),
            ),
            rx.fragment(),
        ),
        variant="soft",
        color_scheme="gray",
        width=rx.cond(SidebarState.collapsed, "36px", "100%"),
        height="36px",
        padding_x=rx.cond(SidebarState.collapsed, "0", "9px"),
        justify_content=rx.cond(SidebarState.collapsed, "center", "flex-start"),
        cursor="pointer",
    )


def _item(icon: str, label: str, **props) -> rx.Component:
    return rx.dropdown_menu.item(
        rx.hstack(
            rx.icon(icon, size=14),
            rx.text(label, size="1"),
            spacing="2",
            align="center",
        ),
        **props,
    )


def _menu() -> rx.Component:
    return rx.dropdown_menu.content(
        _item("key-round", "Credenciais", on_click=CredenciaisState.abrir),
        _item("info", "Sobre", on_click=SobreState.abrir),
        rx.dropdown_menu.separator(),
        rx.dropdown_menu.item(
            rx.hstack(
                rx.color_mode_cond(rx.icon("moon", size=14), rx.icon("sun", size=14)),
                rx.color_mode_cond(
                    rx.text("Modo Escuro", size="1"),
                    rx.text("Modo Claro", size="1"),
                ),
                spacing="2",
                align="center",
            ),
            on_click=rx.toggle_color_mode,
        ),
        side="top",
        align="start",
    )


def app_menu() -> rx.Component:
    return rx.box(
        rx.dropdown_menu.root(
            rx.dropdown_menu.trigger(_trigger(), as_child=True),
            _menu(),
            modal=False,
        ),
        credenciais_dialog(),
        sobre_dialog(),
        width="100%",
        display="flex",
        justify_content="center",
        padding_top="4px",
        padding_bottom="8px",
        padding_x=rx.cond(SidebarState.collapsed, "6px", "8px"),
    )
