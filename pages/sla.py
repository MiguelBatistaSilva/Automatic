"""
pages/sla.py — Aba "Análise de SLA" migrada.

Introduz o padrão "resultado por item numa tabela" além dos logs: o fluxo emite um
`resultado` por chamado, que a ponte entrega ao `_on_evento` para anexar em
`resultados`. Reusa `flow_sla_pw.extrair_historico_chamado` + `sla_engine.calcular_sla`
sem tocar em nada de services.
"""

import dataclasses

import reflex as rx

from services.sla_engine import FILAS, FILA_PADRAO
from states.flow_runner import FlowRunnerState
from components.log_console import log_console
from components.layout import page_layout
from components.form import coluna, duas_colunas, ALTURA_TEXTAREA
from components.botoes import botao_primario


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

        # Credenciais salvas (keyring, via app). Uma pagina de Credenciais entra numa
        # fase posterior; por ora reusa o cofre que o app Qt ja preenche.
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


def _linha_resultado(r: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(r.numero, font_weight="bold"),
        rx.table.cell(r.inicio),
        rx.table.cell(r.tempo),
        rx.table.cell(
            r.status,
            color=rx.cond(r.erro, "#DC2626", "#16A34A"),
            font_weight="bold",
        ),
        rx.table.cell(r.acoes),
    )


def _tabela() -> rx.Component:
    return rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("Chamado"),
                rx.table.column_header_cell("Início"),
                rx.table.column_header_cell("Tempo de SLA"),
                rx.table.column_header_cell("Status"),
                rx.table.column_header_cell("Ações"),
            ),
        ),
        rx.table.body(rx.foreach(SLAState.resultados, _linha_resultado)),
        width="100%",
        variant="surface",
    )


def sla_page() -> rx.Component:
    conteudo = rx.vstack(
        rx.heading("Análise de SLA", size="6"),
        rx.text(
            "Calcula o tempo líquido de SLA de cada chamado a partir do histórico de ações.",
            color="#6B7280",
        ),
        # Mesmas colunas do Desmembramento: metade/metade, campo grande à direita.
        duas_colunas(
            coluna(
                rx.text("Fila", weight="bold"),
                rx.select(
                    SLAState.filas,
                    value=SLAState.fila,
                    on_change=SLAState.set_fila,
                    width="100%",
                ),
            ),
            coluna(
                rx.text("Chamados (um por linha)", weight="bold"),
                rx.text_area(
                    placeholder="S2123456\nS2123457\nS2123458",
                    value=SLAState.chamados_texto,
                    on_change=SLAState.set_chamados_texto,
                    height=ALTURA_TEXTAREA,
                    width="100%",
                    font_family="monospace",
                ),
            ),
        ),
        botao_primario(
            "Analisar SLA",
            on_click=SLAState.analisar,
            disabled=SLAState.rodando,
        ),
        rx.heading("Resultados", size="4", margin_top="0.5em"),
        _tabela(),
        rx.heading("Registro de Execução", size="4", margin_top="0.5em"),
        log_console(SLAState.logs),
        spacing="4",
        width="100%",
    )
    return page_layout(conteudo)
