"""
components/topbar.py — Barra horizontal no topo da área de conteúdo.

Separada da sidebar de propósito: é onde mora o que não é navegação nem
configuração de automação (isso já tem lugar — NAV_ITEMS e o menu Opções), mas
também não é chamativo o bastante pra virar rota própria. Hoje só o ícone de
Atualização; se entrar mais alguma coisa aqui, segue o mesmo padrão.
"""

import reflex as rx

from state.update_state import UpdateState
from components.dialog_atualizacao import update_dialog


def _botao_atualizacao() -> rx.Component:
    """A cor muda quando há uma versão nova disponível (UpdateState.disponivel),
    pra chamar atenção sem depender de o usuário abrir o pop-up pra descobrir."""
    return rx.button(
        rx.icon(
            "download",
            size=20,
            color=rx.cond(UpdateState.disponivel, "#16A34A", rx.color("gray", 11)),
        ),
        on_click=UpdateState.abrir,
        variant="ghost",
        color_scheme="gray",
        size="3",
        cursor="pointer",
        title=rx.cond(UpdateState.disponivel, "Atualização disponível", "Verificar atualização"),
    )


def topbar() -> rx.Component:
    return rx.hstack(
        rx.spacer(),
        _botao_atualizacao(),
        update_dialog(),
        width="100%",
        align="center",
        padding="6px 16px",
        min_height="52px",
        border_bottom=f"1px solid {rx.color('gray', 6)}",
        background_color=rx.color("gray", 1),
        flex_shrink="0",
    )
