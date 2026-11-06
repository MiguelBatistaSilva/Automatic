"""
state/agente_bot_state.py — A aba "Agente" da tela do Assistente: liga e desliga o
bot do Telegram e mostra o terminal dele. O processo está em services/bot_processo.py.

O terminal se atualiza por um laço enquanto a aba estiver aberta. O laço tem fim
(30 min) porque um evento em background não percebe a aba do navegador fechar. Cada
laço novo troca `_ronda`, e o anterior para: nunca há dois rodando.
"""

import asyncio
import re
import time
import uuid

import reflex as rx

from state.flow_runner import LogLine

_LINHA = re.compile(r"^\d{4}-\d\d-\d\d (\d\d:\d\d:\d\d),\d+ (\w+) (.*)$")
_TIPOS = {"ERROR": "error", "CRITICAL": "error", "WARNING": "status"}
_ATUALIZAR_S = 2
_DURACAO_S = 30 * 60


def _log_line(texto: str, ts: str) -> LogLine:
    m = _LINHA.match(texto)
    if m:
        return LogLine(ts=m[1], tipo=_TIPOS.get(m[2], "info"), msg=m[3])
    return LogLine(ts=ts, tipo="info", msg=texto)


class AgenteBotState(rx.State):
    aba: str = "chat"
    ligado: bool = False
    tem_token: bool = True
    logs: list[LogLine] = []
    _ronda: str = ""

    def _ler(self) -> None:
        from services import bot_processo
        self.ligado = bot_processo.ligado()
        self.tem_token = bot_processo.tem_token()
        saida, ts = [], ""
        for texto in bot_processo.linhas():
            linha = _log_line(texto, ts)
            ts = linha.ts
            saida.append(linha)
        self.logs = saida

    @rx.event
    def set_aba(self, v: str | list[str]):
        self.aba = v
        if v == "agente":
            self._ler()
            return AgenteBotState.acompanhar

    @rx.event
    def ao_abrir(self):
        if self.aba == "agente":
            self._ler()
            return AgenteBotState.acompanhar

    @rx.event
    def ligar(self):
        from services import bot_processo
        erro = bot_processo.ligar()
        self._ler()
        if erro:
            return rx.toast.error(erro)

    @rx.event
    def desligar(self):
        from services import bot_processo
        bot_processo.desligar()
        self._ler()

    @rx.event(background=True)
    async def acompanhar(self):
        ronda = uuid.uuid4().hex
        async with self:
            self._ronda = ronda
        fim = time.time() + _DURACAO_S
        while time.time() < fim:
            async with self:
                if self.aba != "agente" or self._ronda != ronda:
                    return
                self._ler()
            await asyncio.sleep(_ATUALIZAR_S)
