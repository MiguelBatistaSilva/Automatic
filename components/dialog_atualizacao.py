"""
components/dialog_atualizacao.py — Pop-up "Atualização" (ícone no topo da sidebar).

Três botões, um por etapa do state/update_state.py: Buscar -> Baixar -> Reiniciar
e aplicar. Só a view; o "porquê precisa reiniciar" está documentado lá.
"""

import reflex as rx

from version import VERSION
from state.update_state import UpdateState
from components.botoes import botao_primario, botao_secundario


def update_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Atualização"),
            rx.vstack(
                rx.text(f"Versão instalada: v{VERSION}", color="#6B7280", size="2"),
                botao_primario(
                    "Buscar atualização",
                    on_click=UpdateState.verificar,
                    disabled=UpdateState.verificando | UpdateState.baixando,
                    width="100%",
                    margin_top="0.75em",
                ),
                rx.cond(
                    UpdateState.disponivel & ~UpdateState.pronto_para_reiniciar,
                    botao_secundario(
                        "Baixar atualização",
                        on_click=UpdateState.baixar,
                        disabled=UpdateState.baixando,
                        width="100%",
                        margin_top="0.5em",
                    ),
                ),
                rx.cond(
                    UpdateState.pronto_para_reiniciar,
                    botao_primario(
                        "Reiniciar e aplicar",
                        on_click=UpdateState.aplicar_e_reiniciar,
                        color_scheme="green",
                        width="100%",
                        margin_top="0.5em",
                    ),
                ),
                rx.text(UpdateState.status, color=UpdateState.status_cor, size="2",
                        margin_top="0.5em"),
                spacing="1",
                align_items="stretch",
                width="100%",
            ),
            rx.hstack(
                rx.spacer(),
                rx.dialog.close(botao_secundario("Fechar")),
                width="100%",
                margin_top="1.25em",
            ),
            max_width="380px",
        ),
        open=UpdateState.aberto,
        on_open_change=UpdateState.set_aberto,
    )
