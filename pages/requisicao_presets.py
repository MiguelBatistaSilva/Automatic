"""
pages/requisicao_presets.py — Tela "Presets da Requisição".

Cadastro dos valores fixos que o /requisicao do bot (Telegram) oferece como
BOTÃO em vez de pedir texto digitado. Só a view; o CRUD está em
`state/requisicao_presets_state.py`, sobre `services/requisicao_presets.py`.

Campo sem nenhum valor cadastrado aqui não trava o bot: ele simplesmente pede
texto digitado pra aquele campo (ver bot/commands/cmd_requisicao.py).
"""

import reflex as rx

from state.requisicao_presets_state import RequisicaoPresetsState
from services.requisicao_campos import POR_CHAVE
from services.requisicao_presets import CAMPOS_COM_PRESET
from components.layout import page_layout
from components.botoes import botao_secundario, botao_tabela


def _valor_linha(campo: str):
    def render(valor: rx.Var, idx: rx.Var) -> rx.Component:
        return rx.hstack(
            rx.text(valor, size="2"),
            rx.spacer(),
            botao_tabela(rx.icon("x", size=13),
                        on_click=RequisicaoPresetsState.remover(campo, idx)),
            width="100%",
            align="center",
        )
    return render


def _secao_campo(campo: str) -> rx.Component:
    rotulo = POR_CHAVE[campo].rotulo
    return rx.vstack(
        rx.text(rotulo, weight="bold", size="3"),
        rx.vstack(
            rx.foreach(RequisicaoPresetsState.presets[campo], _valor_linha(campo)),
            rx.cond(
                RequisicaoPresetsState.presets[campo].length() == 0,
                rx.text(
                    "Nenhum valor cadastrado — esse campo vai pedir texto "
                    "digitado no bot.",
                    size="1", color="#6B7280",
                ),
            ),
            width="100%",
            spacing="1",
            align_items="start",
        ),
        rx.hstack(
            rx.input(
                placeholder=f"Novo valor para {rotulo}",
                value=RequisicaoPresetsState.novos_valores[campo],
                on_change=RequisicaoPresetsState.set_novo_valor(campo),
                flex="1",
            ),
            botao_secundario("+ Adicionar", on_click=RequisicaoPresetsState.adicionar(campo)),
            width="100%",
            spacing="2",
        ),
        spacing="2",
        align_items="start",
        width="100%",
        padding="12px",
        border=f"1px solid {rx.color('gray', 6)}",
        border_radius="8px",
    )


def requisicao_presets_page() -> rx.Component:
    conteudo = rx.vstack(
        rx.heading("Presets da Requisição", size="6"),
        rx.text(
            "Valores fixos que aparecem como botão no /requisicao do bot do "
            "Telegram, em vez da pessoa ter que digitar. Usuário afetado e "
            "Descrição não entram aqui — são sempre texto livre, cada "
            "chamado é diferente.",
            color="#6B7280",
        ),
        *[_secao_campo(c) for c in CAMPOS_COM_PRESET],
        rx.text(RequisicaoPresetsState.status, color=RequisicaoPresetsState.status_cor),
        spacing="4",
        width="100%",
        max_width="640px",
    )
    return page_layout(conteudo)
