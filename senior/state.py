"""
senior/state.py — Back-end da página Ponto (Senior HCM).

Site e credencial à parte do Assyst — ver senior/credenciais.py e
senior/service.py. Página SEM entrada na sidebar (components/sidebar.py
NAV_ITEMS): só acessível digitando a rota /senior no navegador.

Laço de agendamento espelha o padrão de state/atendimento_state.py (poll a cada
~20s, fatiado em 1s para o "Parar" responder rápido) — só que aqui os horários são
4 slots fixos do dia, não uma agenda que cresce.
"""

import asyncio
import dataclasses
import time
from datetime import datetime

import reflex as rx

from state.flow_runner import FlowRunnerState

STATUS_PENDENTE = "PENDENTE"
STATUS_EXECUTANDO = "EXECUTANDO"
STATUS_CONCLUIDO = "CONCLUIDO"
STATUS_ERRO = "ERRO"
STATUS_EXPIRADO = "EXPIRADO"


@dataclasses.dataclass
class HorarioItem:
    label: str
    quando_ts: float
    status: str


class PontoState(FlowRunnerState, rx.State):  # mixin + rx.State: logs/rodando proprios
    usuario: str = ""
    senha: str = ""
    mostrar_senha: bool = False
    tem_credencial: bool = False

    mostrar_navegador: bool = True

    horario1: str = ""
    horario2: str = ""
    horario3: str = ""
    horario4: str = ""

    agenda: list[HorarioItem] = []
    armado: bool = False

    cred_status: str = ""
    cred_status_cor: str = "#6B7280"

    @rx.event
    def on_load(self):
        from senior import credenciais

        usuario, senha = credenciais.carregar()
        self.usuario = usuario
        self.senha = senha
        self.tem_credencial = bool(usuario)

    @rx.event
    def set_usuario(self, v: str):
        self.usuario = v

    @rx.event
    def set_senha(self, v: str):
        self.senha = v

    @rx.event
    def toggle_mostrar_senha(self, v: bool):
        self.mostrar_senha = v

    @rx.event
    def toggle_mostrar_navegador(self, v: bool):
        self.mostrar_navegador = v

    @rx.event
    def set_horario1(self, v: str):
        self.horario1 = v

    @rx.event
    def set_horario2(self, v: str):
        self.horario2 = v

    @rx.event
    def set_horario3(self, v: str):
        self.horario3 = v

    @rx.event
    def set_horario4(self, v: str):
        self.horario4 = v

    @rx.event
    def salvar_credencial(self):
        from senior import credenciais

        try:
            credenciais.salvar(self.usuario, self.senha)
        except ValueError as e:
            self.cred_status = str(e)
            self.cred_status_cor = "#DC2626"
            return
        except Exception as e:
            self.cred_status = f"Nao foi possivel gravar no Cofre do Windows: {e}"
            self.cred_status_cor = "#DC2626"
            return
        self.tem_credencial = True
        self.cred_status = "✓ Credencial salva com sucesso."
        self.cred_status_cor = "#16A34A"

    # ------------------------------------------------------------ teste (1x, agora)
    @rx.event(background=True)
    async def testar(self, clicar: bool):
        async with self:
            if self.rodando:
                return
            usuario, senha = self.usuario, self.senha
            headless = not self.mostrar_navegador
            self.logs = []
            self.rodando = True
        yield

        if not usuario or not senha:
            async with self:
                self.logs = self.logs + [self._linha("Credencial nao cadastrada (salve acima).", "error")]
                self.rodando = False
            return

        def worker(log, emit):
            from senior.service import testar
            testar(usuario, senha, log, clicar=clicar, headless=headless)

        async for _ in self._rodar_sync(worker):
            yield

        async with self:
            self.rodando = False
        yield

    # ------------------------------------------------------------ arm/disarm
    @rx.event
    def desarmar(self):
        self.armado = False
        self.logs = self.logs + [self._linha("Agendamento pausado.", "status")]

    @rx.event(background=True)
    async def armar(self):
        from senior.service import validar_horario

        async with self:
            if self.armado:
                return
            if not self.usuario or not self.senha:
                self.logs = self.logs + [self._linha("Credencial nao cadastrada (salve acima).", "error")]
                return

            textos = [self.horario1, self.horario2, self.horario3, self.horario4]
            horarios = []
            for texto in textos:
                if not texto.strip():
                    continue
                dt = validar_horario(texto)
                if dt is None:
                    self.logs = self.logs + [self._linha(f"Horario invalido: '{texto}'.", "error")]
                    return
                horarios.append(dt)
            if not horarios:
                self.logs = self.logs + [self._linha("Informe ao menos um horario.", "error")]
                return
            horarios.sort()

            self.agenda = [
                HorarioItem(label=h.strftime("%H:%M"), quando_ts=h.timestamp(), status=STATUS_PENDENTE)
                for h in horarios
            ]
            self.armado = True
            self.logs = self.logs + [self._linha(
                f"Agendamento ativado para {len(horarios)} horario(s).", "success")]

        usuario, senha = self.usuario, self.senha
        headless = not self.mostrar_navegador
        yield

        tolerancia_s = 60  # TOLERANCIA_MINUTOS do senior/service.py, em segundos

        while True:
            async with self:
                if not self.armado:
                    break
                agora = time.time()
                vencido_idx = next(
                    (i for i, a in enumerate(self.agenda)
                     if a.status == STATUS_PENDENTE and a.quando_ts <= agora),
                    None,
                )
                rodar = vencido_idx is not None and not self.rodando
                if rodar:
                    item = self.agenda[vencido_idx]
                    expirado = agora > item.quando_ts + tolerancia_s
                    novo_status = STATUS_EXPIRADO if expirado else STATUS_EXECUTANDO
                    self.agenda = [
                        dataclasses.replace(a, status=novo_status) if i == vencido_idx else a
                        for i, a in enumerate(self.agenda)
                    ]
                    if expirado:
                        self.logs = self.logs + [self._linha(
                            f"Horario {item.label} ja passou (tolerancia de 1 min). Pulando.", "error")]
                        rodar = False
                    else:
                        self.rodando = True

            if rodar:
                yield  # empurra o status EXECUTANDO
                idx = vencido_idx

                def worker(log, emit):
                    from senior.service import testar
                    ok = testar(usuario, senha, log, clicar=True, headless=headless)
                    emit("resultado", (idx, ok))

                async for _ in self._rodar_sync(worker, on_evento=self._on_resultado):
                    yield
                async with self:
                    self.rodando = False
                yield
            else:
                yield

            # Dorme ~20s, fatiado para responder ao desarmar em <=1s.
            for _ in range(20):
                async with self:
                    if not self.armado or not any(a.status == STATUS_PENDENTE for a in self.agenda):
                        break
                await asyncio.sleep(1)

            async with self:
                if not any(a.status == STATUS_PENDENTE for a in self.agenda):
                    if self.armado:
                        self.logs = self.logs + [self._linha("Todos os horarios foram processados.", "status")]
                        self.armado = False
                    break

    async def _on_resultado(self, kind, payload):
        if kind == "resultado":
            idx, sucesso = payload
            async with self:
                self.agenda = [
                    dataclasses.replace(a, status=(STATUS_CONCLUIDO if sucesso else STATUS_ERRO))
                    if i == idx else a
                    for i, a in enumerate(self.agenda)
                ]
