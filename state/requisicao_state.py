"""
state/requisicao_state.py — Back-end da página "Requisição de Serviço".

Cria chamados DO ZERO a partir de um bloco colado: uma requisição por linha, campos
separados por `;` e na ordem de `ORDEM_COLUNAS`. Reusa `flow_requisicao_pw` inteiro
(`parse_entrada` + `criar_requisicao`) — services não sabe que existe UI.

Segue o padrão "resultado por item numa tabela" da Análise de SLA: o worker emite um
`resultado` por linha, que `_on_evento` anexa em `resultados`.

**A entrada é validada ANTES de abrir o navegador.** `parse_entrada` levanta com o
número da linha; mostrar isso na hora é muito melhor do que descobrir no meio do lote,
com metade dos chamados já criados — aqui cada execução ABRE CHAMADO DE VERDADE, e não
há como desfazer.

A aba SEMPRE salva. O `modo_teste` do `criar_requisicao` continua existindo, mas só
para o `teste_requisicao.py`: decisão do usuário de não expor esse botão ao operador.
"""

import dataclasses

import reflex as rx

from services.flow_requisicao_pw import parse_entrada
from services.requisicao_campos import ORDEM_COLUNAS, POR_CHAVE, SEPARADOR
from state.flow_runner import FlowRunnerState

# Ajuda da tela, DERIVADA do contrato (nunca escrita à mão): se a ordem mudar no
# catálogo, a tela acompanha sozinha em vez de mentir.
# `EXEMPLO_ORDEM` são os rótulos na ordem — vira o placeholder da caixa.
ORDEM_ROTULOS: list[str] = [POR_CHAVE[c].rotulo for c in ORDEM_COLUNAS]
EXEMPLO_ORDEM: str = f"{SEPARADOR} ".join(ORDEM_ROTULOS)

# `EXEMPLO_PREENCHIDO` é uma linha de verdade, mostrada abaixo da caixa. Vai colada no
# `;`, sem espaço depois, para o exemplo mostrar o formato mínimo — o `parse_linha` dá
# `strip()` em cada valor, então espaço em volta do separador é indiferente.
_EXEMPLO_VALORES: tuple[str, ...] = (
    "905245",
    "Fórum Clóvis Beviláqua",
    "Troca de periférico",
    "Usuário relatou que o mouse não funciona.",
    "Notebook",
    "IC NÃO LOCALIZADO",
    "Instalação",   # Categoria: os valores usados sao "Instalação" e "Configuração"
    "2N CATI FCB",
    "Miguel Batista da Silva",
)
EXEMPLO_PREENCHIDO: str = SEPARADOR.join(_EXEMPLO_VALORES)


@dataclasses.dataclass
class RequisicaoResultado:
    """Uma linha da tabela de resultados (tipada: `dict` quebra o rx.foreach)."""

    linha: str      # "1", "2"... — casa com a linha colada pelo operador
    usuario: str    # Usuário afetado, para reconhecer a requisição de relance
    numero: str     # chamado criado ("--" quando falhou)
    status: str
    erro: bool


class RequisicaoState(FlowRunnerState, rx.State):  # mixin + rx.State: logs/rodando próprios
    entrada_texto: str = ""
    resultados: list[RequisicaoResultado] = []

    @rx.event
    def set_entrada_texto(self, v: str):
        self.entrada_texto = v

    async def _on_evento(self, kind: str, payload):
        if kind == "resultado":
            async with self:
                self.resultados = self.resultados + [payload]

    @rx.event(background=True)
    async def iniciar(self):
        async with self:
            if self.rodando:
                return
            texto = self.entrada_texto
            self.logs = []
            self.resultados = []
            self.rodando = True

        # -- Validação da entrada, antes de qualquer navegador --
        try:
            requisicoes = parse_entrada(texto)
        except ValueError as e:
            async with self:
                self.logs = self.logs + [self._linha(str(e), "error")]
                self.rodando = False
            return

        if not requisicoes:
            async with self:
                self.logs = self.logs + [self._linha(
                    "Cole ao menos uma linha.", "error")]
                self.rodando = False
            return

        from services import credenciais
        matricula, senha = credenciais.carregar()
        if not matricula or not senha:
            async with self:
                self.logs = self.logs + [self._linha(
                    "Credenciais nao cadastradas (configure em Opções → Credenciais).",
                    "error")]
                self.rodando = False
            return

        def worker(log, emit):
            from services.browser_pw import NavegadorPW, _fazer_login_pw
            from services.flow_requisicao_pw import criar_requisicao

            total = len(requisicoes)
            log(f"Iniciando {total} requisição(ões)...", "status")

            with NavegadorPW(log) as page:
                if not _fazer_login_pw(page, matricula, senha, log):
                    for i, valores in enumerate(requisicoes, 1):
                        emit("resultado", RequisicaoResultado(
                            linha=str(i), usuario=valores.get("usuario_afetado", "--"),
                            numero="--", status="✗ Falha no login", erro=True))
                    return

                for i, valores in enumerate(requisicoes, 1):
                    usuario = valores.get("usuario_afetado", "--")
                    log(f"[{i}/{total}] Requisição para {usuario}...", "status")

                    # A aba SEMPRE salva: o `modo_teste` do fluxo existe so para o
                    # `teste_requisicao.py` (decisao do usuario — o operador nao deve
                    # ter esse botao). Contrato: None = falhou, str = numero criado.
                    numero = criar_requisicao(page, log, valores)

                    if numero is None:
                        status, erro, mostrado = "✗ Falhou", True, "--"
                    else:
                        status, erro, mostrado = "✓ Criada", False, numero

                    emit("resultado", RequisicaoResultado(
                        linha=str(i), usuario=usuario, numero=mostrado,
                        status=status, erro=erro))

        async for _ in self._rodar_sync(worker, on_evento=self._on_evento):
            yield

        async with self:
            self.rodando = False
        yield
