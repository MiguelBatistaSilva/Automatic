"""
state/plantoes_state.py — Back-end da página Plantões Judiciários (18/11).

Só lê e grava a escala em services/plantoes.py: quem cria as Requisições é o
Sentinela de lá, no backend. A tela lê o banco ao abrir, a cada ação e no
botão Atualizar.
"""

import asyncio
import dataclasses
import datetime
import time
import uuid

import reflex as rx

from services import plantoes
from state.flow_runner import LogLine

# Enquanto a página está aberta, relê o banco (o Sentinela roda no backend).
_ATUALIZAR_S = 3
_DURACAO_S = 60 * 60


@dataclasses.dataclass
class LinhaPlantao:
    local: str
    dia: str          # ISO (chave no banco)
    rotulo: str       # "sáb 22/11"
    data: str         # "22/11/2026"
    tecnico: str
    aviso: str        # técnico fora da fila do local


@dataclasses.dataclass
class ResultadoPlantao:
    local: str        # "NAC Caucaia · sáb 28/11"
    tecnico: str
    numero: str       # chamado criado ("--" se ainda não)
    status: str       # Programado | Criado | Criado, não programado | Não criado
    cor: str


@dataclasses.dataclass
class DiaPlantao:
    dia: str
    rotulo: str       # "sex 20/11 · Consciência Negra"
    fixo: bool        # sábado/domingo: não sai


@dataclasses.dataclass
class DiaExtra:
    dia: str
    rotulo: str       # "08/12/2026 · Dia da Justiça"


class PlantoesState(rx.State):
    grupo: str = "capital"     # segmented control: "capital" | "interior"
    logs: list[LogLine] = []   # do bloco escolhido (services/plantoes.registrar)
    resultados: list[ResultadoPlantao] = []   # do bloco escolhido
    _ronda: str = ""
    linhas: list[LinhaPlantao] = []
    dias: list[DiaPlantao] = []
    tecnicos: list[str] = []
    supervisor: str = ""
    supervisor_nac: str = ""
    # Pop-up "Cadastrar matrículas" (23/11): rascunho, só grava no Salvar.
    sup_capital: str = ""
    sup_nac: str = ""
    matriculas_aberto: bool = False
    ligado: bool = False
    fase: str = ""            # do bloco escolhido
    travada: bool = False     # bloco escolhido já começou (técnicos travam)
    dias_travados: bool = False   # algum bloco começou (dias travam)
    info: str = ""
    falta: str = ""
    pendente: dict[str, str] = {}   # local -> "Falta: sáb 21/11, ..." ("" = completo)
    resumo: str = ""
    hora_hora: str = plantoes.HORA_FIXA_PADRAO["hora"]
    inicio: str = ""          # "qui 19/11" (véspera do 1º dia)
    extras: list[DiaExtra] = []
    extra_dia: str = ""
    extra_nome: str = ""

    def _ler(self) -> None:
        from services.agente.ferramentas.requisicao import _aviso_fila, _opcoes
        e = plantoes.estado()
        s = e["sentinela"]
        op = _opcoes()
        self.tecnicos = op["tecnicos"]
        self.supervisor = plantoes.supervisor()
        self.supervisor_nac = plantoes.supervisor(nac=True)
        ds = plantoes.datas(e)
        fer = plantoes.feriados({d.year for d in ds})
        self.dias = [DiaPlantao(d.isoformat(),
                                plantoes.rotulo_dia(d) + (f" · {fer[d]}" if d in fer else ""),
                                d.weekday() >= 5)
                     for d in ds]
        hoje = datetime.date.today().isoformat()
        self.extras = [DiaExtra(iso, f"{datetime.date.fromisoformat(iso):%d/%m/%Y} · {n}")
                       for iso, n in plantoes.dias_extras().items() if iso >= hoje]
        self.linhas = [
            LinhaPlantao(chave, d.isoformat(), plantoes.rotulo_dia(d), f"{d:%d/%m/%Y}",
                         cel["tecnico"],
                         _aviso_fila(cel["tecnico"], fila) if cel["tecnico"] else "")
            for chave, *_, fila in plantoes._locais_da(e) for d in ds
            for cel in [e["escala"][chave][d.isoformat()]]
        ]
        self.logs = [LogLine(ts=l.get("ts", ""), tipo=l.get("tipo", "info"), msg=l.get("msg", ""))
                     for l in plantoes.linhas_log(self.grupo)]
        self.resultados = [ResultadoPlantao(**r) for r in plantoes.resultados(e, self.grupo)]
        self.ligado = bool(s.get("ligado"))
        b = e["blocos"][self.grupo]
        self.fase = b.get("fase") or ""
        self.travada = plantoes._travado(e, self.grupo)
        self.dias_travados = plantoes._travada(e)
        self.resumo = b.get("resumo") or ""
        hf = s.get("hora_fixa") or plantoes.HORA_FIXA_PADRAO
        self.hora_hora = hf["hora"]
        self.falta = "" if self.supervisor else "Falta a matrícula do supervisor."
        self.pendente = {c: "" for c, *_ in plantoes.LOCAIS}
        for chave, *_ in plantoes._locais_da(e):
            dias = [plantoes.rotulo_dia(d) for d in ds
                    if not e["escala"][chave][d.isoformat()].get("tecnico")]
            self.pendente[chave] = ("Falta o técnico em: " + ", ".join(dias) + ".") if dias else ""
        fixo = plantoes.momento_fixo(e)
        self.inicio = plantoes.rotulo_dia(fixo.date())
        completa = not plantoes.faltando(e, self.grupo)
        passou = datetime.datetime.now() >= fixo
        nome = plantoes.NOME_GRUPO[self.grupo]
        if not self.ligado:
            self.info = ""
        elif self.fase == plantoes.CRIANDO:
            self.info = f"{nome}: criando as Requisições agora..."
        elif self.fase == plantoes.CONCLUIDO:
            self.info = f"{nome}: plantões criados ({b.get('quando', '')})."
        elif self.fase == plantoes.ERRO:
            self.info = f"{nome}: a criação parou no meio. Confira o resultado."
        elif passou and completa:
            self.info = f"{nome} completo: iniciando em instantes..."
        elif passou:
            self.info = f"{nome}: passou do horário e está incompleto. Inicia assim que completar."
        elif completa:
            self.info = f"{nome} completo: inicia {self.inicio} às {self.hora_hora}."
        else:
            self.info = f"{nome}: inicia {self.inicio} às {self.hora_hora}, se estiver completo."

    @rx.event
    def carregar(self):
        self._ler()
        return PlantoesState.acompanhar

    @rx.event(background=True)
    async def acompanhar(self):
        """Relê a escala e o log a cada poucos segundos (1 h no máximo; abrir a
        página de novo recomeça). Ronda nova para a anterior."""
        ronda = uuid.uuid4().hex
        async with self:
            self._ronda = ronda
        fim = time.time() + _DURACAO_S
        while time.time() < fim:
            await asyncio.sleep(_ATUALIZAR_S)
            async with self:
                if self._ronda != ronda:
                    return
                # "Inicia às" pode estar sendo digitado: não atropela.
                hora = self.hora_hora
                self._ler()
                self.hora_hora = hora

    @rx.event
    def set_grupo(self, v):
        self.grupo = v if v in plantoes.GRUPOS else "capital"
        self._ler()

    def _depois(self, erro: str):
        self._ler()
        if erro:
            return rx.toast.error(erro)

    @rx.event
    def definir(self, local: str, dia: str, campo: str, valor: str):
        return self._depois(plantoes.definir(local, dia, campo, valor))

    @rx.event
    def abrir_matriculas(self, aberto: bool = True):
        self._ler()
        self.sup_capital = self.supervisor
        self.sup_nac = self.supervisor_nac
        self.matriculas_aberto = aberto

    @rx.event
    def set_sup_capital(self, v: str):
        self.sup_capital = v

    @rx.event
    def set_sup_nac(self, v: str):
        self.sup_nac = v

    @rx.event
    def salvar_matriculas(self):
        import re
        cap = re.sub(r"\D", "", self.sup_capital)
        nac = re.sub(r"\D", "", self.sup_nac)
        # 27/11: cada matrícula salva sozinha. Exigir as duas impedia gravar a
        # da capital e o bloco Capital não saía (o Interior cobra a dele).
        if not cap and not nac:
            return rx.toast.error("Informe ao menos uma matrícula.")
        erro = ""
        for m, e_nac in ((cap, False), (nac, True)):
            if m and m != plantoes.supervisor(nac=e_nac):
                erro = plantoes.definir_supervisor(m, e_nac) or erro
        self._ler()
        if erro:
            return rx.toast.error(erro)
        self.matriculas_aberto = False
        return rx.toast.success("Matrículas salvas.")

    @rx.event
    def remover_dia(self, dia: str):
        return self._depois(plantoes.remover_dia(dia))

    @rx.event
    def set_extra_dia(self, v: str):
        self.extra_dia = v

    @rx.event
    def set_extra_nome(self, v: str):
        self.extra_nome = v

    @rx.event
    def adicionar_extra(self):
        try:
            d = datetime.date.fromisoformat(self.extra_dia)
        except ValueError:
            return rx.toast.error("Escolha a data do dia.")
        erro = plantoes.adicionar_extra(d, self.extra_nome)
        if not erro or erro.startswith("Cadastrado"):
            self.extra_dia = self.extra_nome = ""
        return self._depois(erro)

    @rx.event
    def remover_extra(self, dia: str):
        plantoes.remover_extra(dia)
        self._ler()

    @rx.event
    def alternar(self):
        from services.dados import credenciais
        if self.ligado:
            plantoes.desligar()
            self._ler()
            return rx.toast.info("Sentinela dos plantões desligado.")
        matricula, senha = credenciais.carregar()
        if not matricula or not senha:
            return rx.toast.error("Credenciais não cadastradas (configure no app).")
        plantoes.ligar(matricula)
        self._ler()
        return rx.toast.success("Sentinela dos plantões ligado.")

    @rx.event
    def set_hora_hora(self, v: str):
        self.hora_hora = v

    @rx.event
    def salvar_hora(self):
        return self._depois(plantoes.definir_hora_fixa(self.hora_hora))

    @rx.event
    def tentar_de_novo(self):
        plantoes.tentar_de_novo(self.grupo)
        self._ler()
        return rx.toast.info("Vai tentar de novo em até 30 s (as já criadas são puladas).")
