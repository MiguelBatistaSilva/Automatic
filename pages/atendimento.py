"""
pages/atendimento.py — Aba "Iniciar Atendimento" migrada.

O técnico agenda chamados (em Atendimento Programado) para iniciar numa data/hora;
quando bate a hora, o fluxo `flow_atendimento_pw.iniciar_atendimento` roda.

Migração do timer: o `QTimer(20s)` do Qt vira um **laço em background event**
(`while armado: checar vencidos; rodar lote; dormir ~20s`). Como um background event
não pode ficar preso, o `desarmar` só baixa a flag `armado` e o laço percebe em ≤1s
(o sleep de 20s é fatiado em 1s para responder rápido).

Dois cuidados frente ao Qt:
  - a SENHA não vai para state var (o Reflex serializa a state ao navegador) — ela é
    relida do keyring a cada lote, nunca guardada;
  - mutar um campo de dataclass in-place NÃO dispara re-render no Reflex; por isso a
    agenda é atualizada com `dataclasses.replace` reatribuindo a lista inteira.

Reusa `flow_atendimento_pw` sem tocar em nada de services.
"""

import asyncio
import dataclasses
import time
from datetime import datetime

import reflex as rx

from states.flow_runner import FlowRunnerState
from components.log_console import log_console
from components.layout import page_layout
from components.botoes import botao_primario, botao_secundario, botao_icone

_PENDENTE = "PENDENTE"
_EXECUTANDO = "EXECUTANDO"
_CONCLUIDO = "CONCLUIDO"
_ERRO = "ERRO"


@dataclasses.dataclass
class AgendaItem:
    chamado: str
    quando_ts: float     # epoch — comparação no laço (backend)
    quando_label: str    # exibição
    status: str


class AtendimentoState(FlowRunnerState, rx.State):  # mixin + rx.State: logs/rodando proprios
    agenda: list[AgendaItem] = []
    novo_chamado: str = ""
    data_hora: str = ""     # input datetime-local -> "2026-07-25T14:30"
    armado: bool = False

    # setters
    @rx.event
    def set_novo_chamado(self, v: str):
        self.novo_chamado = v

    @rx.event
    def set_data_hora(self, v: str):
        self.data_hora = v

    # ------------------------------------------------------------ agenda
    @rx.event
    def adicionar(self):
        chamado = self.novo_chamado.strip()
        if not chamado:
            self.logs = self.logs + [self._linha("Informe o número do chamado antes de agendar.", "error")]
            return
        if not self.data_hora:
            self.logs = self.logs + [self._linha("Informe a data e hora.", "error")]
            return
        try:
            dt = datetime.fromisoformat(self.data_hora).replace(second=0, microsecond=0)
        except ValueError:
            self.logs = self.logs + [self._linha("Data/hora inválida.", "error")]
            return
        item = AgendaItem(
            chamado=chamado,
            quando_ts=dt.timestamp(),
            quando_label=dt.strftime("%d/%m/%Y %H:%M"),
            status=_PENDENTE,
        )
        self.agenda = self.agenda + [item]
        self.logs = self.logs + [self._linha(
            f"Agendado: {chamado} para {item.quando_label}.", "info")]
        self.novo_chamado = ""

    @rx.event
    def remover(self, idx: int):
        item = self.agenda[idx]
        if item.status == _EXECUTANDO:
            self.logs = self.logs + [self._linha("Não é possível remover um item em execução.", "error")]
            return
        self.agenda = [a for i, a in enumerate(self.agenda) if i != idx]

    # ------------------------------------------------------------ arm/disarm
    @rx.event
    def desarmar(self):
        self.armado = False
        self.logs = self.logs + [self._linha("Agendamento pausado.", "status")]

    async def _on_resultado(self, kind, payload):
        if kind == "resultado":
            chamado, sucesso = payload
            async with self:
                self.agenda = [
                    dataclasses.replace(a, status=(_CONCLUIDO if sucesso else _ERRO))
                    if (a.chamado == chamado and a.status == _EXECUTANDO) else a
                    for a in self.agenda
                ]

    @rx.event(background=True)
    async def armar(self):
        async with self:
            if self.armado:
                return
            if not any(a.status == _PENDENTE for a in self.agenda):
                self.logs = self.logs + [self._linha("Agende ao menos um chamado pendente.", "error")]
                return
            self.armado = True
            self.logs = self.logs + [self._linha("Agendamento ativado. Verificando a cada 20s.", "success")]

        # Valida credenciais uma vez (relidas a cada lote; nunca guardadas).
        from services import credenciais
        mat, senha = credenciais.carregar()
        if not mat or not senha:
            async with self:
                self.armado = False
                self.logs = self.logs + [self._linha(
                    "Credenciais nao cadastradas (configure no app).", "error")]
            yield
            return
        yield

        while True:
            async with self:
                if not self.armado:
                    break
                agora = time.time()
                vencidos = [a.chamado for a in self.agenda
                            if a.status == _PENDENTE and a.quando_ts <= agora]
                rodar = bool(vencidos) and not self.rodando
                if rodar:
                    self.agenda = [
                        dataclasses.replace(a, status=_EXECUTANDO)
                        if (a.status == _PENDENTE and a.quando_ts <= agora) else a
                        for a in self.agenda
                    ]
                    self.rodando = True

            if rodar:
                yield  # empurra o status EXECUTANDO para a tabela
                matricula, senha = credenciais.carregar()
                chamados = vencidos

                def worker(log, emit):
                    from services.browser_pw import NavegadorPW, _fazer_login_pw
                    from services.flow_atendimento_pw import iniciar_atendimento, DESCRICAO_PADRAO
                    with NavegadorPW(log) as page:
                        if not _fazer_login_pw(page, matricula, senha, log):
                            for c in chamados:
                                emit("resultado", (c, False))
                            return
                        for chamado in chamados:
                            log(f"Iniciando atendimento do chamado {chamado}...", "status")
                            ok = iniciar_atendimento(page, log, chamado, DESCRICAO_PADRAO, False)
                            emit("resultado", (chamado, ok))

                async for _ in self._rodar_sync(worker, on_evento=self._on_resultado):
                    yield
                async with self:
                    self.rodando = False
                yield

            # Dorme ~20s, mas fatiado para responder ao desarmar em ≤1s.
            for _ in range(20):
                async with self:
                    if not self.armado:
                        break
                await asyncio.sleep(1)


# --------------------------------------------------------------------- UI

def _badge_status(status: rx.Var) -> rx.Component:
    """Status como badge colorido. Um rx.match por estado porque o `color_scheme`
    do badge e um literal — nao aceita Var."""
    return rx.match(
        status,
        (_EXECUTANDO, rx.badge("Executando", color_scheme="cyan")),
        (_CONCLUIDO, rx.badge("Concluído", color_scheme="green")),
        (_ERRO, rx.badge("Erro", color_scheme="red")),
        rx.badge("Pendente", color_scheme="gray"),
    )


def _linha_agenda(item: rx.Var, idx: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(item.chamado),
        rx.table.cell(item.quando_label),
        rx.table.cell(_badge_status(item.status)),
        rx.table.cell(
            botao_icone(
                "x",
                on_click=AtendimentoState.remover(idx),
                title="Remover da agenda",
            ),
        ),
    )


def _tabela_agenda() -> rx.Component:
    return rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("Chamado"),
                rx.table.column_header_cell("Agendado para"),
                rx.table.column_header_cell("Status"),
                rx.table.column_header_cell(""),
            ),
        ),
        rx.table.body(rx.foreach(AtendimentoState.agenda, _linha_agenda)),
        width="100%",
        variant="surface",
    )


def atendimento_page() -> rx.Component:
    conteudo = rx.vstack(
        rx.heading("Iniciar Atendimento", size="6"),
        rx.text(
            "Agende chamados em Atendimento Programado; quando bate a hora, o fluxo inicia o atendimento.",
            color="#6B7280",
        ),
        rx.hstack(
            rx.vstack(
                rx.text("Chamado", weight="bold"),
                rx.input(
                    placeholder="S2397518",
                    value=AtendimentoState.novo_chamado,
                    on_change=AtendimentoState.set_novo_chamado,
                ),
                rx.text("Iniciar em (dia e hora)", weight="bold", margin_top="0.5em"),
                rx.input(
                    type="datetime-local",
                    value=AtendimentoState.data_hora,
                    on_change=AtendimentoState.set_data_hora,
                ),
                botao_secundario("Agendar", on_click=AtendimentoState.adicionar,
                                 margin_top="0.5em"),
                rx.cond(
                    AtendimentoState.armado,
                    botao_primario("Pausar agendamento", on_click=AtendimentoState.desarmar,
                                   color_scheme="amber", margin_top="0.5em"),
                    botao_primario("Ativar agendamento", on_click=AtendimentoState.armar,
                                   margin_top="0.5em"),
                ),
                spacing="1",
                align_items="stretch",
                width="260px",
            ),
            rx.vstack(
                rx.text("Agenda", weight="bold"),
                _tabela_agenda(),
                spacing="2",
                align_items="stretch",
                flex="1",
            ),
            spacing="5",
            width="100%",
            align_items="start",
        ),
        rx.heading("Registro de Execução", size="4", margin_top="0.5em"),
        log_console(AtendimentoState.logs),
        spacing="4",
        width="100%",
    )
    return page_layout(conteudo)
