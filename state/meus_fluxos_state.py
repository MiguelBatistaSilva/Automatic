"""
state/meus_fluxos_state.py — Back-end da página "Meus fluxos".

Histórico dos fluxos que a matrícula logada rodou — lido direto dos checkpoints
(`checkpoint.historico`), que desde a v5 do banco (2026-09-29) guardam cada
rodada com fluxo/origem/matrícula e não apagam mais a anterior no "Do zero".
Só leitura, com uma exceção (16/11): o botão "Retomar" das rodadas de
Desmembramento pela metade abre o lote na tela do Desmembramento, que é quem
roda (com o diálogo de checkpoint de sempre).

Filtra pela matrícula das Credenciais (app_config) — na máquina do bot, as
rodadas que OUTROS técnicos disparam pelo bot ficam de fora (decisão do
usuário, 2026-09-29). Rodadas de antes da v5 não têm matrícula e não aparecem.

Os fluxos sem checkpoint (Informação, Fornecedor, Usuário, Atendimento)
não entram por enquanto.
"""

import dataclasses

import reflex as rx

FLUXOS: dict[str, str] = {
    "desmembramento_completo": "Desmembramento · Criar + Base",
    "desmembramento_criar":    "Desmembramento · Só Criar",
    "desmembramento_bc":       "Desmembramento · Só Base",
    "desmembramento":          "Desmembramento",
    # Memória por lote (services/dados/memoria_lote.py), 16/11.
    "desmembramento_itom":     "Desmembramento · Adicionar Itom",
    "desmembramento_doc":      "Desmembramento · Importar documento",
    "desmembramento_itemb":    "Desmembramento · Corrigir Item B",
    "correcao_chamado":        "Correção (Edifício/Item B)",
    "requisicao":              "Requisição de Serviço",
    # Sentinela da página Plantões Judiciários (24/11).
    "plantoes_capital":        "Plantões · Capital",
    "plantoes_interior":       "Plantões · Interior",
}

FILTRO_TODOS = "Todos"
FILTROS_FLUXO: list[str] = [FILTRO_TODOS, "Desmembramento", "Requisição de Serviço", "Plantões"]
FILTROS_STATUS: list[str] = [FILTRO_TODOS, "Em andamento", "Concluído", "Substituído"]

_STATUS_LINHA = {
    "concluido": ("Concluído", "green"),
    "salvo":     ("Salvo — falta a Base", "amber"),
    "pendente":  ("Pendente", "gray"),
}


@dataclasses.dataclass
class LinhaFluxo:
    linha: str
    referencia: str   # chamado (Só Base) ou usuário afetado (Requisição)
    gerado: str       # chamado criado — "" se não houve
    status: str
    cor: str


@dataclasses.dataclass
class Rodada:
    id: int
    fluxo: str
    titulo: str
    origem: str
    quando: str
    status: str
    cor: str
    progresso: str
    linhas: list[LinhaFluxo]
    chave: str = ""
    # "Retomar" (16/11): rodada vigente pela metade, de Desmembramento, com os
    # dados do lote guardados (services/dados/memoria_lote.py).
    retomavel: bool = False


def _titulo(h: dict) -> str:
    # A própria chave do checkpoint: chamado pai no Desmembramento, hash no Só
    # Base (bc_...) e na Requisição (req_...) — decisão do usuário; os chamados
    # aparecem ao abrir a rodada.
    return h["chave"]


def _status(h: dict) -> tuple[str, str]:
    if h["concluido"]:
        return "Concluído", "green"
    if not h["vigente"]:
        # Um "Do zero" posterior da mesma chave tomou o lugar desta rodada.
        return "Substituído", "gray"
    return "Em andamento", "amber"


def _rodada(h: dict, com_dados: set[str] = frozenset()) -> Rodada:
    status, cor = _status(h)
    feitas = sum(1 for l in h["linhas"] if l["status"] == "concluido")
    linhas = []
    for l in h["linhas"]:
        st, c = _STATUS_LINHA.get(l["status"], (l["status"], "gray"))
        linhas.append(LinhaFluxo(
            linha=str(l["index"] + 1),
            referencia=l.get("referencia") or l.get("usuario", ""),
            # Desmembramento guarda o filho em numero_filho; a Requisição, em `numero`.
            gerado=l.get("numero_filho") or l.get("numero", ""),
            status=st,
            cor=c,
        ))
    return Rodada(
        id=h["id"],
        fluxo=FLUXOS.get(h["fluxo"], h["fluxo"] or "—"),
        titulo=_titulo(h),
        origem="Bot" if h["origem"] == "bot" else "App",
        quando=h["criado_em"],
        status=status,
        cor=cor,
        progresso=f"{feitas}/{h['total']}",
        linhas=linhas,
        chave=h["chave"],
        retomavel=(h["vigente"] and not h["concluido"] and h["chave"] in com_dados
                   and (h["fluxo"] or "").startswith("desmembramento")),
    )


class MeusFluxosState(rx.State):
    rodadas: list[Rodada] = []
    matricula: str = ""
    filtro_fluxo: str = FILTRO_TODOS
    filtro_status: str = FILTRO_TODOS
    aberta: int = -1

    @rx.event
    def on_load(self):
        from services.dados import checkpoint, credenciais, memoria_lote
        self.matricula = credenciais._ler_matricula()
        hist = checkpoint.historico(self.matricula) if self.matricula else []
        com_dados = memoria_lote.chaves_com_parametros(
            list({h["chave"] for h in hist if h["vigente"] and not h["concluido"]}))
        self.rodadas = [_rodada(h, com_dados) for h in hist]

    @rx.event
    def retomar(self, chave: str):
        """Abre o lote na tela do Desmembramento, já preenchido, com o diálogo
        de checkpoint (o Retomar de lá roda só os pendentes)."""
        from services.dados import memoria_lote
        from state.desmembramento_state import DesmembramentoState
        p = memoria_lote.parametros(chave)
        if not p:
            return rx.toast.error("Os dados deste lote não foram guardados.")
        return [DesmembramentoState.carregar_lote(p), rx.redirect("/desmembramento")]

    @rx.event
    def set_filtro_fluxo(self, v: str):
        self.filtro_fluxo = v

    @rx.event
    def set_filtro_status(self, v: str):
        self.filtro_status = v

    @rx.event
    def alternar(self, rodada_id: int):
        self.aberta = -1 if self.aberta == rodada_id else rodada_id

    @rx.var
    def filtradas(self) -> list[Rodada]:
        return [
            r for r in self.rodadas
            if (self.filtro_fluxo == FILTRO_TODOS or r.fluxo.startswith(self.filtro_fluxo))
            and (self.filtro_status == FILTRO_TODOS or r.status == self.filtro_status)
        ]
