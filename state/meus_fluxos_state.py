"""
state/meus_fluxos_state.py — Back-end da página "Meus fluxos".

Histórico dos fluxos que a matrícula logada rodou — lido direto dos checkpoints
(`checkpoint.historico`), que desde a v5 do banco (2026-09-29) guardam cada
rodada com fluxo/origem/matrícula e não apagam mais a anterior no "Do zero".
Só leitura: nada aqui retoma ou altera fluxo.

Filtra pela matrícula das Credenciais (app_config) — na máquina do bot, as
rodadas que OUTROS técnicos disparam pelo bot ficam de fora (decisão do
usuário, 2026-09-29). Rodadas de antes da v5 não têm matrícula e não aparecem.

Os fluxos sem checkpoint (/informacao, /fornecedor, /infousuario, Atendimento)
não entram por enquanto.
"""

import dataclasses

import reflex as rx

FLUXOS: dict[str, str] = {
    "desmembramento_completo": "Desmembramento · Criar + Base",
    "desmembramento_criar":    "Desmembramento · Só Criar",
    "desmembramento_bc":       "Desmembramento · Só Base",
    "desmembramento":          "Desmembramento",
    "requisicao":              "Requisição de Serviço",
}

FILTRO_TODOS = "Todos"
FILTROS_FLUXO: list[str] = [FILTRO_TODOS, "Desmembramento", "Requisição de Serviço"]
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


def _rodada(h: dict) -> Rodada:
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
    )


class MeusFluxosState(rx.State):
    rodadas: list[Rodada] = []
    matricula: str = ""
    filtro_fluxo: str = FILTRO_TODOS
    filtro_status: str = FILTRO_TODOS
    aberta: int = -1

    @rx.event
    def on_load(self):
        from services import checkpoint, credenciais
        self.matricula = credenciais._ler_matricula()
        self.rodadas = (
            [_rodada(h) for h in checkpoint.historico(self.matricula)]
            if self.matricula else []
        )

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
