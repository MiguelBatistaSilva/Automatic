"""
state/sla_state.py — Back-end da página Análise de SLA.

Introduz o padrão "resultado por item numa tabela" além dos logs: o fluxo emite um
`resultado` por chamado, que a ponte entrega ao `_on_evento` para anexar em
`resultados`. Reusa `flow_sla_pw.extrair_historico_chamado` + `sla_engine.calcular_sla`
sem tocar em nada de services.
"""

import dataclasses

import reflex as rx

from services.sla_engine import FILAS, FILA_PADRAO, HORA_INICIO, HORA_FIM
from state.flow_runner import FlowRunnerState

# ── Resumo das regras, para a ajuda da tela ────────────────────────────────────
# DERIVADO do `sla_engine`, nunca escrito à mão: é o mesmo dicionário que o cálculo
# usa. Se um prazo mudar lá, a tela acompanha — o contrário seria uma ajuda que
# mente, e ninguém confere ajuda contra código.


@dataclasses.dataclass(frozen=True)
class FilaInfo:
    nome: str
    prazo: str
    fim_de_semana: str
    corre_no_fds: bool


EXPEDIENTE: str = f"{HORA_INICIO:02d}:00 às {HORA_FIM:02d}:00"

FILAS_INFO: list[FilaInfo] = [
    FilaInfo(
        nome=nome,
        prazo=f"{cfg['limite_horas']}h",
        fim_de_semana="Conta" if cfg["conta_fim_de_semana"] else "Congela",
        corre_no_fds=cfg["conta_fim_de_semana"],
    )
    for nome, cfg in FILAS.items()
]


@dataclasses.dataclass
class SLAResultado:
    numero: str
    inicio: str
    tempo: str
    status: str
    acoes: str
    erro: bool  # True -> status em vermelho (falha de execucao OU SLA estourado)


class SLAState(FlowRunnerState, rx.State):  # mixin + rx.State: logs/rodando proprios
    chamados_texto: str = ""
    fila: str = FILA_PADRAO
    filas: list[str] = list(FILAS.keys())
    resultados: list[SLAResultado] = []

    @rx.event
    def set_chamados_texto(self, v: str):
        self.chamados_texto = v

    @rx.event
    def set_fila(self, v: str):
        self.fila = v

    async def _on_evento(self, kind: str, payload):
        if kind == "resultado":
            async with self:
                self.resultados = self.resultados + [payload]

    @rx.event(background=True)
    async def analisar(self):
        async with self:
            if self.rodando:
                return
            chamados = [l.strip() for l in self.chamados_texto.splitlines() if l.strip()]
            fila = self.fila
            self.logs = []
            self.resultados = []
            self.rodando = True

        if not chamados:
            async with self:
                self.logs = self.logs + [self._linha("Preencha ao menos um chamado.", "error")]
                self.rodando = False
            return

        # Credenciais salvas (keyring), cadastradas no pop-up Opcoes -> Credenciais.
        from services import credenciais
        matricula, senha = credenciais.carregar()
        if not matricula or not senha:
            async with self:
                self.logs = self.logs + [self._linha(
                    "Credenciais nao cadastradas (configure no app).", "error")]
                self.rodando = False
            return

        def worker(log, emit):
            from services.browser_pw import NavegadorPW, _fazer_login_pw
            from services.flow_sla_pw import extrair_historico_chamado
            from services.sla_engine import calcular_sla

            log(f"Iniciando analise de {len(chamados)} chamado(s)...", "status")
            with NavegadorPW(log) as page:
                if not _fazer_login_pw(page, matricula, senha, log):
                    for c in chamados:
                        emit("resultado", SLAResultado(
                            numero=c, inicio="--", tempo="--",
                            status="✗ Falha no login", acoes="--", erro=True))
                    return

                total = len(chamados)
                for i, numero in enumerate(chamados, 1):
                    log(f"[{i}/{total}] Analisando {numero}...", "status")
                    historico = extrair_historico_chamado(page, numero, log)
                    if historico is None:
                        emit("resultado", SLAResultado(
                            numero=numero, inicio="--", tempo="--",
                            status="✗ Falha ao extrair historico", acoes="--", erro=True))
                        continue
                    r = calcular_sla(historico, fila)
                    emit("resultado", SLAResultado(
                        numero=numero,
                        inicio=r.get("inicio", "--"),
                        tempo=r.get("tempo_gasto_str", "--"),
                        status=r.get("mensagem", "--"),
                        acoes=str(len(historico)),
                        erro=r.get("estourado", False),
                    ))

        async for _ in self._rodar_sync(worker, on_evento=self._on_evento):
            yield

        async with self:
            self.rodando = False
        yield
