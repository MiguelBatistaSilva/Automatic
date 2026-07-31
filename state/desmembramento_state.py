"""
state/desmembramento_state.py — Back-end da página Desmembramento (3 modos).

Modos (mesma semântica do antigo aba_execucao.py do Qt):
  - completo : Criar + Base   -> FluxoCompletoPW
  - criar    : Só Criar (3N)  -> FluxoCriarPW
  - bc       : Só Base        -> FluxoBCPW

Ponto delicado: o **diálogo de checkpoint**. Um evento background async não pode
parar no meio esperando o clique do usuário; então `iniciar` (evento SYNC) valida e
checa o checkpoint e, se precisar decidir, ABRE o diálogo e para. Os botões do
diálogo disparam `executar(iniciar_do_zero)` em background. Sem checkpoint pendente,
`iniciar` dispara `executar(False)` direto.

Reusa `flow_desmembramento_pw`, `kb_manager_pw`, `checkpoint`, `kb_store` — services
intactos. Não há tabela de resultados: o fluxo é guiado por logs + checkpoint, e
abre o TXT de filhos ao final (os.startfile, na máquina do operador).
"""

import csv
import io

import reflex as rx

from services.checkpoint import existe_pendente, foi_concluido, resumo as resumo_checkpoint
from services.flow_desmembramento_pw import _chave_checkpoint
from state.flow_runner import FlowRunnerState

DESCRICAO_PADRAO = "Solicito atualização de sistema..."


def _parse_csv(texto: str):
    """Devolve (colunas, linhas) a partir do CSV colado (1a linha = cabecalho)."""
    rows = list(csv.reader(io.StringIO(texto.strip())))
    if not rows:
        return [], []
    colunas = [c.strip() for c in rows[0]]
    linhas = [
        [v.strip() for v in row]
        for row in rows[1:]
        if any(v.strip() for v in row)
    ]
    return colunas, linhas


class DesmembramentoState(FlowRunnerState, rx.State):  # mixin + rx.State: logs/rodando proprios
    modo: str = "completo"
    chamado_pai: str = ""
    descricao: str = DESCRICAO_PADRAO
    csv_texto: str = ""
    filhos_texto: str = ""
    kb_selecionado: str = ""
    kbs: list[str] = []

    # Diálogo de checkpoint
    cp_aberto: bool = False
    cp_modo: str = ""      # "pendente" | "concluido"
    cp_resumo: str = ""
    cp_label: str = ""

    @rx.event
    def on_load(self):
        from services import kb_store
        entries = kb_store.carregar()
        self.kbs = [e["nome_artigo"] for e in entries]

    # setters
    @rx.event
    def set_modo(self, v: str | list[str]):
        # O segmented_control declara on_change como str | list[str] (suporta
        # multi-seleção); aqui é single, então normalizamos para str.
        self.modo = v if isinstance(v, str) else (v[0] if v else "completo")

    @rx.event
    def set_chamado_pai(self, v: str):
        self.chamado_pai = v

    @rx.event
    def set_descricao(self, v: str):
        self.descricao = v

    @rx.event
    def set_csv_texto(self, v: str):
        self.csv_texto = v

    @rx.event
    def set_filhos_texto(self, v: str):
        self.filhos_texto = v

    @rx.event
    def set_kb(self, v: str):
        self.kb_selecionado = v

    # ---------------------------------------------------------------- helpers
    def _filhos(self) -> list[str]:
        return [l.strip() for l in self.filhos_texto.splitlines() if l.strip()]

    def _validar(self) -> list[str]:
        erros = []
        if self.modo in ("completo", "criar"):
            if not self.chamado_pai.strip():
                erros.append("Preencha o número do chamado de Referência.")
            if not _parse_csv(self.csv_texto)[1]:
                erros.append("Cole o CSV (cabeçalho + ao menos uma linha).")
        if self.modo in ("completo", "bc"):
            if not self.kb_selecionado:
                erros.append("Selecione uma Base de Conhecimento.")
        if self.modo == "bc" and not self._filhos():
            erros.append("Cole a lista de chamados filhos.")
        return erros

    def _chave(self) -> str:
        if self.modo == "bc":
            return _chave_checkpoint(self._filhos())
        return self.chamado_pai.strip()

    def _label(self) -> str:
        if self.modo == "bc":
            filhos = self._filhos()
            return filhos[0] if filhos else ""
        return self.chamado_pai.strip()

    # ---------------------------------------------------------------- iniciar
    @rx.event
    def iniciar(self):
        erros = self._validar()
        if erros:
            self.logs = self.logs + [self._linha(e, "error") for e in erros]
            return

        chave = self._chave()
        if foi_concluido(chave):
            self.cp_modo = "concluido"
            self.cp_label = self._label()
            self.cp_aberto = True
            return
        if existe_pendente(chave):
            self.cp_modo = "pendente"
            self.cp_label = self._label()
            self.cp_resumo = resumo_checkpoint(chave)
            self.cp_aberto = True
            return
        return DesmembramentoState.executar(False)

    # botões do diálogo
    @rx.event
    def cp_cancelar(self):
        self.cp_aberto = False

    @rx.event
    def cp_retomar(self):
        self.cp_aberto = False
        return DesmembramentoState.executar(False)

    @rx.event
    def cp_do_zero(self):
        self.cp_aberto = False
        return DesmembramentoState.executar(True)

    # ---------------------------------------------------------------- executar
    @rx.event(background=True)
    async def executar(self, iniciar_do_zero: bool):
        async with self:
            if self.rodando:
                return
            modo = self.modo
            chamado = self.chamado_pai.strip()
            descricao = self.descricao
            csv_texto = self.csv_texto
            filhos = self._filhos()
            kb_nome = self.kb_selecionado
            self.logs = []
            self.rodando = True

        from services import credenciais
        matricula, senha = credenciais.carregar()
        if not matricula or not senha:
            async with self:
                self.logs = self.logs + [self._linha(
                    "Credenciais nao cadastradas (configure no app).", "error")]
                self.rodando = False
            return

        # Monta o kb_config a partir do nome selecionado (lê o kb_store fresco).
        kb_config = None
        if modo in ("completo", "bc"):
            from services import kb_store
            entry = next((e for e in kb_store.carregar() if e["nome_artigo"] == kb_nome), None)
            if not entry:
                async with self:
                    self.logs = self.logs + [self._linha("Base de Conhecimento não encontrada.", "error")]
                    self.rodando = False
                return
            kb_config = {"keyword": entry["keyword"], "nome_artigo": entry["nome_artigo"]}

        # DataFrame para os modos que iteram CSV.
        df = None
        if modo in ("completo", "criar"):
            import pandas as pd
            colunas, linhas = _parse_csv(csv_texto)
            df = pd.DataFrame(linhas, columns=colunas)

        def worker(log, emit):
            from services.browser_pw import NavegadorPW
            from services.kb_manager_pw import executar_kb_unica_pw
            from services.flow_desmembramento_pw import (
                FluxoCompletoPW, FluxoCriarPW, FluxoBCPW,
            )
            # Só Base navega para o próximo chamado logo depois da BC, então não
            # precisa voltar à tela do evento — e era ali que ele travava. Criar+Base
            # precisa: a duplicação da linha seguinte parte do evento aberto.
            voltar = modo != "bc"
            kb_function = (
                lambda p, l: executar_kb_unica_pw(p, l, kb_config, voltar_ao_evento=voltar)
            ) if kb_config else None

            with NavegadorPW(log) as page:
                if modo == "completo":
                    FluxoCompletoPW(page, matricula, senha, log).executar(
                        df=df, descricao_base=descricao, numero_chamado=chamado,
                        kb_function=kb_function, iniciar_do_zero=iniciar_do_zero,
                    )
                elif modo == "criar":
                    FluxoCriarPW(page, matricula, senha, log).executar(
                        df=df, descricao_base=descricao, numero_chamado=chamado,
                        iniciar_do_zero=iniciar_do_zero,
                    )
                else:  # bc
                    FluxoBCPW(page, matricula, senha, log).executar(
                        filhos=filhos, kb_function=kb_function,
                        iniciar_do_zero=iniciar_do_zero,
                    )

        async for _ in self._rodar_sync(worker):
            yield

        async with self:
            self.rodando = False
        yield
