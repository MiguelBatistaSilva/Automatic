"""
components/topbar.py — Barra horizontal no topo da área de conteúdo.

Separada da sidebar de propósito: é onde mora o que não é navegação nem
configuração de automação (isso já tem lugar — NAV_ITEMS e o menu Opções), mas
também não é chamativo o bastante pra virar rota própria.

O ícone de Atualização saiu em 07/10 (o auto-update pela tela vivia dando erro).
Atualizar é pelo `atualizar_automatic.bat`, com o app fechado — ver `atualizar.py`.
Desde 06/11 aqui mora só o aviso de que há versão nova. Na barra, e não acima dela,
para não mudar a altura de que a tela do Assistente depende.
"""

import reflex as rx

from state.atualizacao_state import AtualizacaoState


def _aviso() -> rx.Component:
    return rx.cond(
        AtualizacaoState.versao_nova != "",
        rx.callout(
            "Atualização disponível: versão " + AtualizacaoState.versao_nova
            + ". Feche o Automatic e abra o atualizar_automatic.bat.",
            icon="circle-arrow-up",
            size="1",
            color_scheme="amber",
        ),
    )


def topbar() -> rx.Component:
    return rx.hstack(
        rx.spacer(),
        _aviso(),
        rx.spacer(),
        on_mount=AtualizacaoState.verificar,
        width="100%",
        align="center",
        padding="6px 16px",
        min_height="52px",
        border_bottom=f"1px solid {rx.color('gray', 6)}",
        background_color=rx.color("gray", 1),
        flex_shrink="0",
    )
