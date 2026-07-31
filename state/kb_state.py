"""
state/kb_state.py — Back-end da página Bases de Conhecimento (CRUD).

Lista/adiciona/remove as bases (keyword + nome_artigo) persistidas em `kb_store`.
Sem fluxo/navegador — é só edição de dados; usa rx.State direto (não FlowRunnerState).

A página Desmembramento relê o kb_store no seu on_load (ao navegar), então não é
preciso um sinal cruzado como o `kbs_atualizadas` do Qt.
"""

import dataclasses

import reflex as rx


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
