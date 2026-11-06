"""
state/atendimento_state.py — Back-end da página Iniciar Atendimento.

O técnico agenda chamados (em Atendimento Programado) para iniciar numa data/hora.
A agenda é a mesma do Assistente: a tabela `tarefas` do banco, por
`services/agente/agendados.py`. Quem inicia é o vigia de lá, que roda no backend,
então não há mais o botão de ativar nem o laço nesta tela (05/11): antes a agenda
vivia só na memória da tela e se perdia ao reiniciar.

A tabela não se atualiza sozinha: lê o banco ao abrir a tela, a cada ação e no
botão Atualizar.
"""

import dataclasses
from datetime import datetime

import reflex as rx

from services.agente import agendados


@dataclasses.dataclass
class AgendaItem:
    chamado: str
    quando_label: str
    status: str
    detalhe: str


class AtendimentoState(rx.State):
    agenda: list[AgendaItem] = []
    novo_chamado: str = ""
    data_hora: str = ""     # input datetime-local -> "2026-07-25T14:30"

    # setters
    @rx.event
    def set_novo_chamado(self, v: str):
        self.novo_chamado = v

    @rx.event
    def set_data_hora(self, v: str):
        self.data_hora = v

    def _ler_agenda(self) -> None:
        from services.dados import credenciais
        pendentes, encerrados = agendados.listar(credenciais._ler_matricula())
        self.agenda = [AgendaItem(t["chamado"], t["quando"], t["status"], t["detalhe"])
                       for t in pendentes + encerrados]

    @rx.event
    def carregar(self):
        self._ler_agenda()

    @rx.event
    def adicionar(self):
        from services.dados import credenciais
        chamado = self.novo_chamado.strip()
        if not chamado:
            return rx.toast.error("Informe o número do chamado antes de agendar.")
        if not self.data_hora:
            return rx.toast.error("Informe a data e hora.")
        try:
            dt = datetime.fromisoformat(self.data_hora).replace(second=0, microsecond=0)
        except ValueError:
            return rx.toast.error("Data/hora inválida.")
        if dt <= datetime.now():
            return rx.toast.error("Essa data e hora já passaram.")
        matricula = credenciais._ler_matricula()
        if not matricula:
            return rx.toast.error("Credenciais não cadastradas (configure no app).")
        agendados.agendar(chamado, dt, matricula)
        self.novo_chamado = ""
        self._ler_agenda()

    @rx.event
    def remover(self, chamado: str):
        from services.dados import credenciais
        feitos = agendados.cancelar([chamado], credenciais._ler_matricula())
        self._ler_agenda()
        if not feitos:
            return rx.toast.error("Esse início não está mais pendente.")
