"""Sidebar — menu lateral expansível/contraível.

Espelha o padrão do projeto Asset Management: navegação ORIENTADA A DADOS (uma lista
de NavItem gera tudo num loop — adicionar página é UMA linha), sidebar colapsável com
toggle, destaque de rota REATIVO (via router), cores nativas do tema (rx.color, então
funciona em claro/escuro) e ícones lucide. O rodapé traz o dropdown de opções.
"""

import reflex as rx
from dataclasses import dataclass

from state.sidebar_state import SidebarState
from components.app_menu import app_menu
from components.theme import SIDEBAR_EXPANDED, SIDEBAR_COLLAPSED


# ── Navegação (orientada a dados) ───────────────────────────────────────────────

@dataclass
class NavItem:
    icon: str    # nome do ícone (lucide)
    label: str   # texto que aparece
    href: str    # rota de destino


NAV_ITEMS: list[NavItem] = [
    NavItem("file-plus", "Requisição de Serviço", "/requisicao"),
    NavItem("circle-play", "Iniciar Atendimento", "/atendimento"),
    NavItem("copy", "Desmembramento", "/desmembramento"),
    NavItem("timer", "Análise de SLA", "/sla"),
    NavItem("key-round", "Licenças", "/"),
    NavItem("book-open", "Bases de Conhecimento", "/kb"),
]


# ── Peças internas ──────────────────────────────────────────────────────────────

_OUTRAS_ROTAS = [i.href for i in NAV_ITEMS if i.href != "/"]


def _e_ativo(href: str):
    """Item ativo? Compara com a rota atual — menos a raiz.

    A raiz ("/") nao pode ser comparada por igualdade: o caminho que o router
    devolve nela nao e "/" (nem vazio), entao o item Licencas nunca acendia. Aqui
    ela e ativa por EXCLUSAO — quando a rota atual nao e nenhuma das outras. Assim
    o realce funciona seja qual for a string que a raiz produza.
    """
    if href != "/":
        return SidebarState.active_route == href
    ativo = SidebarState.active_route != _OUTRAS_ROTAS[0]
    for outra in _OUTRAS_ROTAS[1:]:
        ativo = ativo & (SidebarState.active_route != outra)
    return ativo


def _menu_item(item: NavItem) -> rx.Component:
    is_active = _e_ativo(item.href)
    return rx.link(
        rx.hstack(
            rx.icon(item.icon, size=16, color=rx.color("gray", 11), flex_shrink="0"),
            rx.cond(
                ~SidebarState.collapsed,
                rx.text(
                    item.label,
                    size="1",
                    font_size="13px",  # size="1" = 12px; +1px (o "2" já pula p/ 14px)
                    color=rx.color("gray", 11),
                    font_weight=rx.cond(is_active, "600", "400"),
                    white_space="nowrap",
                ),
                rx.fragment(),
            ),
            align="center",
            spacing="2",
            padding_y="7px",
            # Contraída: ícone centrado na coluna (alinha com o toggle e o menu de opções).
            padding_x=rx.cond(SidebarState.collapsed, "0", "9px"),
            justify_content=rx.cond(SidebarState.collapsed, "center", "flex-start"),
            border_radius="6px",
            width="100%",
            background_color=rx.cond(is_active, rx.color("gray", 4), "transparent"),
            _hover={"background_color": rx.cond(is_active, rx.color("gray", 4), rx.color("gray", 3))},
        ),
        href=item.href,
        text_decoration="none",
        width="100%",
        display="block",
    )


def _header() -> rx.Component:
    expanded = rx.hstack(
        rx.text(
            "Automatic",
            size="4",
            font_weight="700",
            color=rx.color("gray", 12),
            white_space="nowrap",
            overflow="hidden",
        ),
        rx.spacer(),
        rx.button(
            rx.icon("panel-left", size=15),
            on_click=SidebarState.toggle,
            variant="ghost",
            color_scheme="gray",
            size="1",
            cursor="pointer",
        ),
        width="100%",
        align="center",
        padding="10px 8px",
        min_height="44px",
    )

    collapsed = rx.box(
        rx.icon("panel-left", size=16, color=rx.color("gray", 11)),
        on_click=SidebarState.toggle,
        width="100%",
        min_height="44px",
        display="flex",
        align_items="center",
        justify_content="center",
        cursor="pointer",
    )

    return rx.box(
        rx.cond(~SidebarState.collapsed, expanded, collapsed),
        padding_x="4px",
        width="100%",
    )


def _nav() -> rx.Component:
    return rx.vstack(
        *[_menu_item(item) for item in NAV_ITEMS],
        spacing="0",
        gap="1px",  # os tokens do Radix pulam de 4 em 4px; 1px vai inline mesmo
        width="100%",
        padding_x="4px",
    )


# ── API pública ───────────────────────────────────────────────────────────────

def sidebar() -> rx.Component:
    return rx.box(
        rx.vstack(
            _header(),
            _nav(),
            rx.spacer(),
            rx.box(rx.divider(), padding_x="8px", width="100%"),
            app_menu(),
            height="100%",
            width="100%",
            spacing="2",
            align="start",
            padding_top="12px",
        ),
        background_color=rx.color("gray", 2),
        border_right=f"1px solid {rx.color('gray', 6)}",
        height="100vh",
        width=rx.cond(SidebarState.collapsed, SIDEBAR_COLLAPSED, SIDEBAR_EXPANDED),
        min_width=rx.cond(SidebarState.collapsed, SIDEBAR_COLLAPSED, SIDEBAR_EXPANDED),
        transition="width 0.2s ease, min-width 0.2s ease",
        overflow="hidden",
        position="sticky",
        top="0",
        flex_shrink="0",
    )
