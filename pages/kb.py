"""
pages/kb.py — Tela da aba "Bases de Conhecimento".

Só a view: tabela das bases cadastradas e formulário de inclusão. O back-end (CRUD
sobre o `kb_store`) está em `state/kb_state.py`.
"""

import reflex as rx

from state.kb_state import KBState
from components.layout import page_layout
from components.botoes import botao_primario, botao_tabela


def _linha(item: rx.Var, idx: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(item.nome_artigo),
        rx.table.cell(rx.code(item.keyword)),
        rx.table.cell(
            botao_tabela("Remover", on_click=KBState.remover(idx)),
        ),
    )


def kb_page() -> rx.Component:
    conteudo = rx.vstack(
        rx.heading("Bases de Conhecimento", size="6"),
        rx.text("Bases usadas pelos modos Criar + Base e Só Base do Desmembramento.",
                color="#6B7280"),

        rx.heading("Bases cadastradas", size="4", margin_top="0.5em"),
        rx.cond(
            KBState.entries,
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Título do Artigo"),
                        rx.table.column_header_cell("Palavra-chave"),
                        rx.table.column_header_cell(""),
                    ),
                ),
                rx.table.body(rx.foreach(KBState.entries, _linha)),
                width="100%",
                variant="surface",
            ),
            rx.text("Nenhuma base cadastrada ainda.", color="#6B7280"),
        ),

        rx.heading("Adicionar nova base", size="4", margin_top="1em"),
        rx.hstack(
            rx.input(placeholder="Palavra-chave (ex: kaspersky)",
                     value=KBState.novo_keyword, on_change=KBState.set_novo_keyword,
                     width="240px"),
            rx.input(placeholder="Título do artigo (ex: BC - Instalação do Kaspersky)",
                     value=KBState.novo_artigo, on_change=KBState.set_novo_artigo,
                     flex="1"),
            spacing="3",
            width="100%",
        ),
        rx.hstack(
            botao_primario("+ Adicionar Base", on_click=KBState.adicionar,
                           color_scheme="green"),
            rx.text(KBState.status, color=KBState.status_cor),
            spacing="3",
            align_items="center",
        ),
        spacing="4",
        width="100%",   # sem max_width: a tabela ocupa a página toda
    )
    return page_layout(conteudo)
