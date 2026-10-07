"""
components/topbar.py — Barra horizontal no topo da área de conteúdo.

Separada da sidebar de propósito: é onde mora o que não é navegação nem
configuração de automação (isso já tem lugar — NAV_ITEMS e o menu Opções), mas
também não é chamativo o bastante pra virar rota própria.

Vazia desde 07/10: o ícone de Atualização saiu (o auto-update pela tela vivia
dando erro). Atualizar agora é pelo `atualizar_automatic.bat`, com o app
fechado — ver `atualizar.py`.
"""

import reflex as rx


def topbar() -> rx.Component:
    return rx.hstack(
        rx.spacer(),
        width="100%",
        align="center",
        padding="6px 16px",
        min_height="52px",
        border_bottom=f"1px solid {rx.color('gray', 6)}",
        background_color=rx.color("gray", 1),
        flex_shrink="0",
    )
