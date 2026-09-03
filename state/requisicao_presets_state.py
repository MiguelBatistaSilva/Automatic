"""
state/requisicao_presets_state.py — Back-end da página "Presets da Requisição".

CRUD dos valores pré-cadastrados por campo (`services/requisicao_presets`),
usados pelo /requisicao do bot pra virar botão em vez de texto livre. Sem
fluxo/navegador — é só edição de dados, igual ao KBState.
"""
import reflex as rx

from services.requisicao_campos import POR_CHAVE
from services.requisicao_presets import CAMPOS_COM_PRESET


class RequisicaoPresetsState(rx.State):
    presets: dict[str, list[str]] = {c: [] for c in CAMPOS_COM_PRESET}
    novos_valores: dict[str, str] = {c: "" for c in CAMPOS_COM_PRESET}
    status: str = ""
    status_cor: str = "#16A34A"

    @rx.event
    def on_load(self):
        from services import requisicao_presets
        self.presets = requisicao_presets.carregar()
        self.novos_valores = {c: "" for c in CAMPOS_COM_PRESET}
        self.status = ""

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
