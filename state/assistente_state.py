"""
state/assistente_state.py — Back-end da página "Assistente" (chat com IA).

Tudo pelo chat, sem console de logs (decisão do usuário, 2026-09-29): o
progresso de uma execução aparece como UMA linha viva dentro do cartão, e o
resultado chega como mensagem do assistente.

Fluxo de um pedido:
  1. `enviar` manda a conversa ao modelo (services/agente/assistente.py) numa
     thread — a chamada HTTP é bloqueante;
  2. se voltar uma `Acao` que ESCREVE, a mensagem vira um cartão com botões;
     se for só leitura, roda na hora;
  3. `acionar(indice, botao)` roda a ação numa thread dedicada (Playwright
     sync se prende à thread que o criou — mesmo motivo do flow_runner) e
     joga o resultado no chat.

A IA só enxerga o texto da conversa: o resultado da execução (nomes, setores
lidos do Assyst) NÃO volta para ela — só uma nota curta de que a ação rodou.
"""

import asyncio
import dataclasses
import threading

import reflex as rx

_LOGS_VISIVEIS = 6

BOTOES = {
    "confirmar": ("Confirmar", "blue", "solid"),
    "retomar":   ("Retomar", "blue", "solid"),
    "do_zero":   ("Refazer do zero", "red", "soft"),
    "simular":   ("Simular (não salva)", "gray", "soft"),
    "cancelar":  ("Cancelar", "gray", "soft"),
}


@dataclasses.dataclass
class Botao:
    codigo: str
    rotulo: str
    cor: str
    variante: str


@dataclasses.dataclass
class Mensagem:
    papel: str                 # "user" | "assistant"
    texto: str = ""
    # Cartão de ação (vazio = mensagem comum)
    titulo: str = ""
    corpo: str = ""            # as linhas do cartão num markdown só
    aviso: str = ""
    botoes: list[Botao] = dataclasses.field(default_factory=list)
    estado: str = ""           # "" | pendente | rodando | feito | cancelado
    erro: bool = False


def _botoes(acao) -> tuple[list[Botao], str]:
    """Botões do cartão + aviso, conforme o checkpoint (mesmas regras dos
    diálogos da página de Desmembramento e do início da Requisição)."""
    cods: list[str]
    aviso = acao.aviso
    if acao.checkpoint == "corrompido":
        cods, aviso = ["cancelar"], ("O checkpoint deste lote existe mas está "
                                     "ilegível. Não vou rodar: poderia recriar "
                                     "chamados que já existem.")
    elif acao.checkpoint == "concluido":
        if acao.ferramenta == "criar_requisicoes":
            cods = ["cancelar"]
        else:
            cods = ["do_zero", "cancelar"]
            aviso = f"Já foi concluído antes. {aviso}".strip()
    elif acao.checkpoint == "pendente":
        if acao.ferramenta == "criar_requisicoes":
            cods = ["retomar", "simular", "cancelar"]
        else:
            cods = ["retomar", "do_zero", "cancelar"]
            aviso = f"Existe uma execução pela metade: {aviso}".strip()
    else:
        cods = ["confirmar"] + (["simular"] if acao.pode_simular else []) + ["cancelar"]
    return [Botao(c, *BOTOES[c]) for c in cods], aviso


class AssistenteState(rx.State):
    mensagens: list[Mensagem] = []
    entrada: str = ""
    pensando: bool = False
    rodando: bool = False
    status_vivo: str = ""
    # Ultimas linhas de log da execucao em andamento, mostradas discretas
    # abaixo do titulo do fluxo (so enquanto roda).
    logs_vivos: list[str] = []
    tem_chave: bool = False
    # False ate o on_load consultar o Cofre. Sem isto a pagina desenhava a
    # caixa "cole a chave" por um instante e trocava pelo chat (bug de 30/09).
    chave_verificada: bool = False
    nova_chave: str = ""

    # Só no servidor (prefixo _): o histórico que vai para a IA e as ações
    # esperando clique, por índice da mensagem-cartão.
    _historico: list[dict] = []
    _acoes: dict[int, object] = {}

    @rx.event
    def on_load(self):
        from services.agente import llm
        self.tem_chave = bool(llm.carregar_chave())
        self.chave_verificada = True

    @rx.event
    def set_entrada(self, v: str):
        self.entrada = v

    @rx.event
    def set_nova_chave(self, v: str):
        self.nova_chave = v

    @rx.event
    def salvar_chave(self):
        from services.agente import llm
        try:
            llm.salvar_chave(self.nova_chave)
        except ValueError:
            return rx.toast.error("Cole a chave antes de salvar.")
        self.nova_chave = ""
        self.tem_chave = True

    @rx.event
    def nova_conversa(self):
        if self.rodando:
            return rx.toast.warning("Espere a execução atual terminar.")
        self.mensagens = []
        self._historico = []
        self._acoes = {}

    # ------------------------------------------------------------------ chat
    @rx.event(background=True)
    async def enviar(self, _form: dict | None = None):
        async with self:
            texto = self.entrada.strip()
            if not texto or self.pensando:
                return
            self.entrada = ""
            self.mensagens = self.mensagens + [Mensagem(papel="user", texto=texto)]
            self._historico = self._historico + [{"role": "user", "content": texto}]
            historico = list(self._historico)
            self.pensando = True
        yield

        from services.agente.assistente import responder
        from services.agente.llm import ErroLLM
        try:
            r = await asyncio.to_thread(responder, historico)
        except ErroLLM as e:
            async with self:
                self.mensagens = self.mensagens + [
                    Mensagem(papel="assistant", texto=str(e), erro=True)]
                self.pensando = False
            return
        except Exception as e:  # nunca deixar o chat travado em "pensando"
            async with self:
                self.mensagens = self.mensagens + [
                    Mensagem(papel="assistant", texto=f"Erro inesperado: {e}", erro=True)]
                self.pensando = False
            return

        rodar_ja = None
        async with self:
            self.pensando = False
            if r.acao is None:
                self.mensagens = self.mensagens + [Mensagem(papel="assistant", texto=r.texto)]
                self._historico = self._historico + [{"role": "assistant", "content": r.texto}]
                return
            botoes, aviso = _botoes(r.acao)
            cartao = Mensagem(
                papel="assistant", texto=r.texto, titulo=r.acao.titulo,
                corpo="  \n".join(r.acao.linhas), aviso=aviso,
                botoes=botoes if r.acao.escreve else [],
                estado="pendente" if r.acao.escreve else "rodando",
            )
            indice = len(self.mensagens)
            self.mensagens = self.mensagens + [cartao]
            self._acoes = {**self._acoes, indice: r.acao}
            nota = (f"[Mostrei o cartão '{r.acao.titulo}' para o técnico confirmar.]"
                    if r.acao.escreve else f"[Executando '{r.acao.titulo}'.]")
            self._historico = self._historico + [{"role": "assistant", "content": nota}]
            if not r.acao.escreve:
                rodar_ja = indice
        yield
        if rodar_ja is not None:
            async for _ in self._executar(rodar_ja, "confirmar"):
                yield

    @rx.event(background=True)
    async def acionar(self, indice: int, botao: str):
        async for _ in self._executar(indice, botao):
            yield

    async def _executar(self, indice: int, botao: str):
        ocupado = False
        async with self:
            acao = self._acoes.get(indice)
            if acao is None or indice >= len(self.mensagens):
                return
            if botao == "cancelar":
                self._marcar(indice, "cancelado")
                self._historico = self._historico + [
                    {"role": "assistant", "content": f"[O técnico cancelou '{acao.titulo}'.]"}]
                self._acoes = {k: v for k, v in self._acoes.items() if k != indice}
                return
            ocupado = self.rodando
        if ocupado:
            # yield FORA do `async with self` (dentro dele o Reflex segura a
            # trava do state enquanto o evento estiver parado no yield).
            yield rx.toast.warning("Já tem uma execução em andamento.")
            return
        async with self:
            self.rodando = True
            self.status_vivo = "Abrindo o navegador..."
            self.logs_vivos = ["Abrindo o navegador..."]
            self._marcar(indice, "rodando")
            from services import credenciais
            matricula, senha = credenciais.carregar()
        yield

        if not matricula or not senha:
            async with self:
                self._fim(indice, acao, "Credenciais não cadastradas (Opções → "
                                        "Credenciais).", erro=True)
            return

        loop = asyncio.get_running_loop()
        fila: asyncio.Queue = asyncio.Queue()

        def log(m, tipo="info"):
            loop.call_soon_threadsafe(fila.put_nowait, ("log", str(m)))

        def runner():
            from services.agente.ferramentas import executar
            try:
                texto = executar(acao, matricula, senha, log,
                                 modo_teste=(botao == "simular"),
                                 iniciar_do_zero=(botao == "do_zero"))
                loop.call_soon_threadsafe(fila.put_nowait, ("fim", (texto, False)))
            except Exception as e:
                loop.call_soon_threadsafe(fila.put_nowait, ("fim", (f"Erro inesperado: {e}", True)))

        threading.Thread(target=runner, daemon=True).start()
        while True:
            tipo, dado = await fila.get()
            if tipo == "log":
                async with self:
                    self.status_vivo = dado
                    self.logs_vivos = (self.logs_vivos + [dado])[-_LOGS_VISIVEIS:]
                yield
                continue
            texto, erro = dado
            async with self:
                self._fim(indice, acao, texto, erro)
            yield
            return

    def _marcar(self, indice: int, estado: str):
        msgs = list(self.mensagens)
        msgs[indice] = dataclasses.replace(msgs[indice], estado=estado)
        self.mensagens = msgs

    def _fim(self, indice: int, acao, texto: str, erro: bool = False):
        self._marcar(indice, "feito")
        self.mensagens = self.mensagens + [Mensagem(papel="assistant", texto=texto, erro=erro)]
        self._historico = self._historico + [{"role": "assistant", "content": (
            f"[A ação '{acao.titulo}' {'falhou' if erro else 'foi executada'}; "
            "o resultado foi mostrado ao técnico.]")}]
        self._acoes = {k: v for k, v in self._acoes.items() if k != indice}
        self.rodando = False
        self.status_vivo = ""
        self.logs_vivos = []
