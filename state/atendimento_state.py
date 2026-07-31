"""
state/atendimento_state.py — Back-end da página Iniciar Atendimento.

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

from state.flow_runner import FlowRunnerState

# Estados de um item da agenda. A página importa daqui para pintar o badge.
STATUS_PENDENTE = "PENDENTE"
STATUS_EXECUTANDO = "EXECUTANDO"
STATUS_CONCLUIDO = "CONCLUIDO"
STATUS_ERRO = "ERRO"


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
            status=STATUS_PENDENTE,
        )
        self.agenda = self.agenda + [item]
        self.logs = self.logs + [self._linha(
            f"Agendado: {chamado} para {item.quando_label}.", "info")]
        self.novo_chamado = ""

    @rx.event
    def remover(self, idx: int):
        item = self.agenda[idx]
        if item.status == STATUS_EXECUTANDO:
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
                    dataclasses.replace(a, status=(STATUS_CONCLUIDO if sucesso else STATUS_ERRO))
                    if (a.chamado == chamado and a.status == STATUS_EXECUTANDO) else a
                    for a in self.agenda
                ]

    @rx.event(background=True)
    async def armar(self):
        async with self:
            if self.armado:
                return
            if not any(a.status == STATUS_PENDENTE for a in self.agenda):
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
                            if a.status == STATUS_PENDENTE and a.quando_ts <= agora]
                rodar = bool(vencidos) and not self.rodando
                if rodar:
                    self.agenda = [
                        dataclasses.replace(a, status=STATUS_EXECUTANDO)
                        if (a.status == STATUS_PENDENTE and a.quando_ts <= agora) else a
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
