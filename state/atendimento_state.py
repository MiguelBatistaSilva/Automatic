"""
state/atendimento_state.py — Back-end da página Iniciar Atendimento.

O técnico agenda chamados (em Atendimento Programado) para iniciar numa data/hora.
A agenda é a mesma do Assistente: a tabela `tarefas` do banco, por
`services/agente/agendados.py`. Quem inicia é o vigia de lá, que roda no backend,
então não há mais o botão de ativar nem o laço nesta tela (05/11): antes a agenda
vivia só na memória da tela e se perdia ao reiniciar.

18/11: o agendamento manual saiu da tela (o Modo Sentinela agenda pela fila; o
Assistente continua agendando). No lugar, "Varrer agora". A tabela mostra o
usuário afetado.

A tabela não se atualiza sozinha: lê o banco ao abrir a tela, a cada ação e no
botão Atualizar.
"""

import dataclasses

import reflex as rx

from services.agente import agendados


@dataclasses.dataclass
class AgendaItem:
    id: str
    chamado: str
    afetado: str
    quando_label: str
    status: str
    detalhe: str


class AtendimentoState(rx.State):
    agenda: list[AgendaItem] = []
    # Modo Sentinela (13/11): services/agente/sentinela.py
    sentinela_ligado: bool = False
    sentinela_rodando: bool = False
    sentinela_info: str = ""

    def _ler_agenda(self) -> None:
        from services.dados import credenciais
        pendentes, encerrados = agendados.listar(credenciais._ler_matricula())
        self.agenda = [AgendaItem(t["id"], t["chamado"], t["afetado"], t["quando"], t["status"], t["detalhe"])
                       for t in pendentes + encerrados]

    def _ler_sentinela(self) -> None:
        from datetime import datetime as _dt
        from services.agente import sentinela
        e = sentinela.estado()
        self.sentinela_ligado = bool(e.get("ligado"))
        self.sentinela_rodando = self.sentinela_ligado and bool(e.get("rodando"))
        r = e.get("resumo") or {}
        if not self.sentinela_ligado:
            self.sentinela_info = "Varre a fila 2N CATI FCB a cada 5 h e agenda os Programados."
        elif e.get("rodando"):
            self.sentinela_info = f"Varrendo a fila {sentinela.FILA} agora..."
        else:
            proxima = _dt.fromtimestamp(e.get("proxima", 0)).strftime("%d/%m %H:%M")
            ultima = f"Última varredura {r['quando']}" if r else "Ainda não varreu"
            self.sentinela_info = f"{ultima}; próxima {proxima}."

    @rx.event
    def carregar(self):
        self._ler_agenda()
        self._ler_sentinela()

    @rx.event
    def alternar_sentinela(self):
        from services.agente import sentinela
        from services.dados import credenciais
        if self.sentinela_ligado:
            sentinela.desligar()
            self._ler_sentinela()
            return rx.toast.info("Sentinela desligado.")
        matricula, senha = credenciais.carregar()
        if not matricula or not senha:
            return rx.toast.error("Credenciais não cadastradas (configure no app).")
        sentinela.ligar(matricula)
        self._ler_sentinela()
        return rx.toast.success(
            f"Sentinela ligado: a 1ª varredura começa em até 1 min e se repete "
            f"a cada {sentinela.INTERVALO_H} h. Clique em Atualizar para ver.")

    @rx.event
    def varrer_agora(self):
        from services.agente import sentinela
        if not sentinela.varrer_agora():
            self._ler_sentinela()
            if self.sentinela_rodando:
                return rx.toast.info("Já está varrendo a fila.")
            return rx.toast.error("Ligue o Sentry Mode primeiro.")
        self._ler_sentinela()
        return rx.toast.success(
            f"A varredura da fila {sentinela.FILA} começa em até 1 min. "
            "Clique em Atualizar para ver.")

    @rx.event
    def remover(self, id_tarefa: str):
        from services.dados import credenciais
        feito = agendados.excluir(id_tarefa, credenciais._ler_matricula())
        self._ler_agenda()
        if not feito:
            return rx.toast.error("Esse início está em execução agora: não dá para excluir.")
