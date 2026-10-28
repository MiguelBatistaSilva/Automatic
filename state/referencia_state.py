"""
state/referencia_state.py — Back-end da aba "Referência" da página
Configurações (pages/configuracoes.py). Substituiu a aba "Presets" em 28/10.

Mostra e edita as tabelas do banco de referência (services/dados/
referencia.py): itens da Requisição, técnicos, filas e edifícios. A edição
só vale onde há `.git` (`referencia.pode_editar()`): em outra máquina o
próximo update sobrescreveria — lá a aba é só consulta. Editou -> commit ->
o updater leva a todos.

`aba` é estado de UI puro do segmented_control da página (qual aba está
selecionada — "kb", "referencia" ou "usuarios"), sem persistência; mora
aqui porque esta é a página que o `automatic_app.py` associa à rota.
"""
import reflex as rx

# Nome mostrado -> arquivo em conhecimento/referencia/.
TABELAS = {
    "Itens da Requisição": "itens.md",
    "Técnicos": "tecnicos.md",
    "Filas": "filas.md",
    "Edifícios": "edificios.md",
}


class ReferenciaState(rx.State):
    aba: str = "kb"
    tabela: str = "Itens da Requisição"
    colunas: list[str] = []
    busca: str = ""
    visiveis: list[list[str]] = []      # linhas que passam na busca
    total: int = 0
    novo: list[str] = []                # campos da linha nova, um por coluna
    editavel: bool = False
    status: str = ""
    status_cor: str = "#16A34A"

    _linhas: list[list[str]] = []
    _indices: list[int] = []            # visiveis[i] é _linhas[_indices[i]]

    @rx.event
    def on_load(self):
        from services.dados import referencia
        self.aba = "kb"
        self.editavel = referencia.pode_editar()
        self._carregar()

    @rx.event
    def set_aba(self, v: str | list[str]):
        # O segmented_control declara on_change como str | list[str] (suporta
        # multiselect); aqui é sempre single-select, mas o tipo tem que bater.
        self.aba = v if isinstance(v, str) else (v[0] if v else "kb")

    @rx.event
    def set_tabela(self, v: str):
        self.tabela = v
        self.busca = ""
        self._carregar()

    @rx.event
    def set_busca(self, v: str):
        self.busca = v
        self._filtrar()

    @rx.event
    def set_novo(self, i: int, v: str):
        novo = list(self.novo)
        novo[i] = v
        self.novo = novo

    def _carregar(self):
        from services.dados import referencia
        arq = TABELAS[self.tabela]
        self.colunas = referencia.colunas(arq)
        self._linhas = [[l.get(c, "") for c in self.colunas]
                        for l in referencia.linhas(arq)]
        self.novo = [""] * len(self.colunas)
        self.status = ""
        self._filtrar()

    def _filtrar(self):
        from services.dados.referencia import _chave
        alvo = _chave(self.busca)
        self._indices = [i for i, l in enumerate(self._linhas)
                         if not alvo or alvo in _chave(" ".join(l))]
        self.visiveis = [self._linhas[i] for i in self._indices]
        self.total = len(self._linhas)

    def _bloqueado(self) -> bool:
        if not self.editavel:
            self.status = "Edição só na máquina de publicação."
            self.status_cor = "#DC2626"
        return not self.editavel

    def _gravar(self, linhas: list[list[str]], msg: str, cor: str):
        from services.dados import referencia
        referencia.gravar(TABELAS[self.tabela], self.colunas, linhas)
        self._linhas = linhas
        self.status = msg + " Lembre de commitar para levar a todos."
        self.status_cor = cor
        self._filtrar()

    @rx.event
    def adicionar(self):
        if self._bloqueado():
            return
        linha = [v.strip() for v in self.novo]
        if not linha or not linha[0]:
            self.status = f"Preencha ao menos '{self.colunas[0]}'."
            self.status_cor = "#DC2626"
            return
        if linha in self._linhas:
            self.status = "Essa linha já existe."
            self.status_cor = "#DC2626"
            return
        self._gravar(self._linhas + [linha], "Adicionada.", "#16A34A")
        self.novo = [""] * len(self.colunas)

    @rx.event
    def remover(self, idx_visivel: int):
        if self._bloqueado():
            return
        i = self._indices[idx_visivel]
        self._gravar([l for j, l in enumerate(self._linhas) if j != i],
                     "Removida.", "#6B7280")
