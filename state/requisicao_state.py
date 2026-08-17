"""
state/requisicao_state.py — Back-end da página "Requisição de Serviço".

Cria chamados DO ZERO a partir de um bloco colado: uma requisição por linha, campos
separados por `;` e na ordem de `ORDEM_COLUNAS`. Reusa `flow_requisicao_pw` inteiro
(`parse_entrada` + `criar_requisicao`) — services não sabe que existe UI.

Segue o padrão "resultado por item numa tabela" da Análise de SLA: o worker emite um
`resultado` por linha, que `_on_evento` anexa em `resultados`.

**CHECKPOINT (2026-08-13), automático, sem diálogo.** Reusa `services/checkpoint.py`
(mesmo módulo do Desmembramento), com a chave derivada do HASH do texto colado
(`_chave_checkpoint` em `flow_requisicao_pw.py`) — não há chamado-pai pra ancorar
aqui. Ao clicar Iniciar, o `iniciar()` decide sozinho: lote novo (`inicializar`),
lote com pendências (retoma — loga e pula as linhas já concluídas) ou lote já
concluído (não abre o navegador). Decisão do usuário: **sem a mesma retentativa
"na hora" que existe no Desmembramento** — se uma linha falhar mas o resto do lote
continuar rodando, ela só é retentada numa PRÓXIMA execução (que também é
automática, sem precisar de clique extra além de rodar de novo). Isso é
intencional, pensando numa futura hospedagem em servidor: um checkpoint em disco
sobrevive a reinícios de processo; um laço de retentativa em memória não.

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

# `EXEMPLOS_PREENCHIDOS` são linhas de verdade, mostradas abaixo da caixa — cada uma
# ilustra um formato diferente de Item B (ver `_preencher_item_b` no flow), que é o
# campo que mais confunde: pode ser um TOMBO de patrimônio (prefixo `*`, o Assyst
# resolve sozinho quando acha) ou uma PALAVRA/valor de catálogo comum, digitado
# igual aos outros lookups. Vão coladas no `;`, sem espaço depois, para o exemplo
# mostrar o formato mínimo — o `parse_linha` dá `strip()` em cada valor, então
# espaço em volta do separador é indiferente.
# Categoria = "Configuração": "Instalação" NAO EXISTE no Assyst (confirmado pelo
# usuário em 2026-08-13) — não trocar de volta sem validar de novo.
_EXEMPLOS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Item B com tombo conhecido (o Assyst resolve sozinho, sem popup)", (
        "905245",
        "Fórum Clóvis Beviláqua",
        "Troca de periférico",
        "Usuário relatou que o computador funciona.",
        "Computador",
        "*332255",
        "Configuração",
        "2N CATI FCB",
        "Miguel Batista da Silva",
    )),
    ("Item B sem tombo (tombo não localizado ou desconhecido)", (
        "905245",
        "Fórum Clóvis Beviláqua",
        "Troca de periférico",
        "Usuário relatou que o mouse não funciona.",
        "Computador",
        "Teclado / Mouse",
        "Configuração",
        "2N CATI FCB",
        "Miguel Batista da Silva",
    )),
)
EXEMPLOS_PREENCHIDOS: list[tuple[str, str]] = [
    (rotulo, SEPARADOR.join(valores)) for rotulo, valores in _EXEMPLOS
]


@dataclasses.dataclass
class RequisicaoResultado:
    """Uma linha da tabela de resultados (tipada: `dict` quebra o rx.foreach)."""

    linha: str      # "1", "2"... — casa com a linha colada pelo operador
    usuario: str    # NOME do Usuário afetado (lido da tela); matrícula como reserva
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
                # `sorted` por LINHA, nao por ordem de chegada: numa retomada as
                # linhas ja concluidas (recarregadas do checkpoint) e as
                # pendentes desta rodada podem nao ser contiguas — sem isso a
                # linha retentada apareceria no fim da tabela, fora de ordem.
                self.resultados = sorted(
                    self.resultados + [payload], key=lambda r: int(r.linha))

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

        # -- CHECKPOINT — decide sozinho (sem dialogo): lote novo, retomar ou ja
        # concluido. A chave vem do PROPRIO TEXTO colado (nao ha chamado-pai
        # pra ancorar, diferente do Desmembramento) — ver `_chave_checkpoint`.
        from services import checkpoint
        from services.flow_requisicao_pw import _chave_checkpoint

        total = len(requisicoes)
        chave = _chave_checkpoint(texto)

        if checkpoint.esta_corrompido(chave):
            async with self:
                self.logs = self.logs + [self._linha(
                    "Checkpoint deste lote existe mas esta ilegivel. ABORTANDO: "
                    "seguir daqui faria o fluxo tratar isto como lote novo e "
                    f"RECRIAR requisições que já existem. Confira o arquivo em "
                    f"data/checkpoints/{chave}.json antes de rodar de novo.",
                    "error")]
                self.rodando = False
            return

        # Linhas ja concluidas em execucoes anteriores (se houver checkpoint) —
        # usadas tanto pra reconstruir a tabela quanto pra decidir o que falta.
        concluidas_antes = sorted(
            (l for l in checkpoint.status_linhas(chave)
             if l["status"] == checkpoint.STATUS_CONCLUIDO),
            key=lambda l: l["index"],
        )
        resultados_antigos = [
            RequisicaoResultado(
                linha=str(l["index"] + 1), usuario=l.get("usuario", ""),
                numero=l.get("numero", ""), status="✓ Criada", erro=False,
            )
            for l in concluidas_antes
        ]

        if checkpoint.foi_concluido(chave):
            async with self:
                self.resultados = resultados_antigos
                self.logs = self.logs + [self._linha(
                    f"Este lote já foi concluído anteriormente ({total}/{total}). "
                    "Nada a fazer — mude o texto colado para criar um lote novo.",
                    "info")]
                self.rodando = False
            return

        if checkpoint.existe_pendente(chave):
            async with self:
                self.resultados = resultados_antigos
                self.logs = self.logs + [self._linha(
                    f"Retomando lote anterior: {len(concluidas_antes)} de {total} "
                    "já concluídas.", "info")]
        else:
            checkpoint.inicializar(chave, total)

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
            from services import checkpoint as cp

            # So as PENDENTES (0-based no checkpoint, 1-based aqui) — as ja
            # concluidas em rodadas anteriores nao sao retocadas.
            pendentes = [
                (i, valores) for i, valores in enumerate(requisicoes, 1)
                if cp.status_linha(chave, i - 1) != cp.STATUS_CONCLUIDO
            ]
            log(f"Iniciando {len(pendentes)} de {total} requisição(ões) "
                "pendente(s)...", "status")

            with NavegadorPW(log) as page:
                if not _fazer_login_pw(page, matricula, senha, log):
                    for i, valores in pendentes:
                        emit("resultado", RequisicaoResultado(
                            linha=str(i), usuario=valores.get("usuario_afetado", "--"),
                            numero="--", status="✗ Falha no login", erro=True))
                    return

                for i, valores in pendentes:
                    # O que o operador COLOU (a matricula). Serve para o log de
                    # progresso e como reserva na tabela: o nome so existe depois
                    # que o type-ahead resolve a matricula na tela.
                    colado = valores.get("usuario_afetado", "--")
                    log(f"[{i}/{total}] Requisição para {colado}...", "status")

                    # A aba SEMPRE salva: o `modo_teste` do fluxo existe so para o
                    # `teste_requisicao.py` (decisao do usuario — o operador nao deve
                    # ter esse botao). Contrato: None = falhou, RequisicaoCriada = ok.
                    resultado = criar_requisicao(page, log, valores)

                    if resultado is None:
                        status, erro, mostrado = "✗ Falhou", True, "--"
                        usuario = colado  # falhou antes de dar para ler o nome
                    else:
                        status, erro, mostrado = "✓ Criada", False, resultado.numero
                        usuario = resultado.usuario
                        # So aqui o checkpoint sabe que a linha esta feita — se
                        # a execucao morrer logo depois, a proxima rodada nao
                        # recria esta requisicao.
                        cp.marcar_concluido_linha(
                            chave, i - 1, numero=resultado.numero, usuario=usuario)

                    emit("resultado", RequisicaoResultado(
                        linha=str(i), usuario=usuario, numero=mostrado,
                        status=status, erro=erro))

        async for _ in self._rodar_sync(worker, on_evento=self._on_evento):
            yield

        async with self:
            self.rodando = False
        yield
