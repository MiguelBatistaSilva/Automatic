"""
state/requisicao_presets_state.py — Back-end da aba "Presets" da página
Configurações (pages/configuracoes.py; antes "Presets da Requisição",
renomeada em 2026-09-09).

CRUD dos valores pré-cadastrados por campo (`services/requisicao_presets`),
usados pelo /requisicao do bot pra virar botão em vez de texto livre. Sem
fluxo/navegador — é só edição de dados, igual ao KBState.

`aba` é estado de UI puro do segmented_control da página (qual aba está
selecionada — "presets" ou "usuarios") — não persiste em disco, mesmo padrão
do `modo` em `state/desmembramento_state.py`. Mora aqui (e não em
`bot/state.py`, dono da aba "Usuários Autorizados") porque essa é a página
que o `automatic_app.py` associa à rota, e o valor por padrão da aba
("presets") é o que essa classe já representa.
"""
import reflex as rx

from services.requisicao_campos import POR_CHAVE
from services.requisicao_presets import CAMPOS_COM_PRESET


class RequisicaoPresetsState(rx.State):
    presets: dict[str, list[str]] = {c: [] for c in CAMPOS_COM_PRESET}
    novos_valores: dict[str, str] = {c: "" for c in CAMPOS_COM_PRESET}
    status: str = ""
    status_cor: str = "#16A34A"
    aba: str = "presets"

    @rx.event
    def on_load(self):
        from services import requisicao_presets
        self.presets = requisicao_presets.carregar()
        self.novos_valores = {c: "" for c in CAMPOS_COM_PRESET}
        self.status = ""
        self.aba = "presets"

    @rx.event
    def set_aba(self, v: str | list[str]):
        # O segmented_control declara on_change como str | list[str] (suporta
        # multiselect); aqui é sempre single-select, mas o tipo tem que bater.
        self.aba = v if isinstance(v, str) else (v[0] if v else "presets")

    def _salvar_disco(self):
        from services import requisicao_presets
        requisicao_presets.salvar(self.presets)

    @rx.event
    def set_novo_valor(self, campo: str, v: str):
        self.novos_valores = {**self.novos_valores, campo: v}

    @rx.event
    def adicionar(self, campo: str):
        valor = self.novos_valores.get(campo, "").strip()
        if not valor:
            return
        atuais = self.presets.get(campo, [])
        if valor in atuais:
            self.status = f"'{valor}' já está cadastrado em {POR_CHAVE[campo].rotulo}."
            self.status_cor = "#DC2626"
            return
        self.presets = {**self.presets, campo: atuais + [valor]}
        self.novos_valores = {**self.novos_valores, campo: ""}
        self._salvar_disco()
        self.status = f"Adicionado em {POR_CHAVE[campo].rotulo}."
        self.status_cor = "#16A34A"

    @rx.event
    def remover(self, campo: str, idx: int):
        atuais = self.presets.get(campo, [])
        self.presets = {**self.presets, campo: [v for i, v in enumerate(atuais) if i != idx]}
        self._salvar_disco()
        self.status = f"Removido de {POR_CHAVE[campo].rotulo}."
        self.status_cor = "#6B7280"
