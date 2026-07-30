"""
pages/kb.py — Aba "Bases de Conhecimento" migrada (CRUD).

Lista/adiciona/remove as bases (keyword + nome_artigo) persistidas em `kb_store`.
Sem fluxo/navegador — é só edição de dados; usa rx.State direto (não FlowRunnerState).

A aba Desmembramento relê o kb_store no seu on_load (ao navegar), então não é
preciso um sinal cruzado como o `kbs_atualizadas` do Qt.
"""

import dataclasses

import reflex as rx

from components.layout import page_layout
from components.botoes import botao_primario, botao_tabela


@dataclasses.dataclass
class KBEntry:
    nome_artigo: str
    keyword: str


class KBState(rx.State):
    entries: list[KBEntry] = []
    novo_keyword: str = ""
    novo_artigo: str = ""
    status: str = ""
    status_cor: str = "#16A34A"

    @rx.event
    def on_load(self):
        from services import kb_store
        self.entries = [KBEntry(e["nome_artigo"], e["keyword"]) for e in kb_store.carregar()]

    def _salvar_disco(self):
        from services import kb_store
        kb_store.salvar([{"keyword": e.keyword, "nome_artigo": e.nome_artigo} for e in self.entries])

    @rx.event
    def set_novo_keyword(self, v: str):
        self.novo_keyword = v

    @rx.event
    def set_novo_artigo(self, v: str):
        self.novo_artigo = v

    @rx.event
    def adicionar(self):
        keyword = self.novo_keyword.strip()
        artigo = self.novo_artigo.strip()
        if not keyword or not artigo:
            self.status = "Preencha todos os campos."
            self.status_cor = "#DC2626"
            return
        if any(e.nome_artigo == artigo for e in self.entries):
            self.status = "Artigo já cadastrado."
            self.status_cor = "#DC2626"
            return
        self.entries = self.entries + [KBEntry(nome_artigo=artigo, keyword=keyword)]
        self._salvar_disco()
        self.novo_keyword = ""
        self.novo_artigo = ""
        self.status = "Base adicionada com sucesso!"
        self.status_cor = "#16A34A"

    @rx.event
    def remover(self, idx: int):
        self.entries = [e for i, e in enumerate(self.entries) if i != idx]
        self._salvar_disco()
        self.status = "Base removida."
        self.status_cor = "#6B7280"


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
