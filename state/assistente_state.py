"""
state/assistente_state.py — Back-end da página "Assistente" (chat com IA).

Tudo pelo chat, sem console de logs (decisão do usuário, 2026-09-29): o
progresso aparece discreto dentro do cartão (últimas linhas de log), e o
resultado de cada passo chega como mensagem do assistente.

Fluxo de um pedido:
  1. `enviar` manda a conversa ao modelo (services/agente/assistente.py) numa
     thread — a chamada HTTP é bloqueante;
  2. o que volta é um PLANO (uma ou mais ações, 2026-10-01). Se alguma ação
     ESCREVE, o plano vira um cartão com botões; se todas só leem, roda na hora;
  3. `acionar(indice, botao)` roda o plano numa thread dedicada (o Playwright
     sync se prende à thread que o criou — mesmo motivo do flow_runner): os
     passos em FILA, numa Sessao só (um login, uma licença). Se um passo falha,
     os seguintes não rodam.

A IA só enxerga o texto da conversa: o resultado da execução (nomes, setores
lidos do Assyst) NÃO volta para ela — só uma nota curta de como o plano terminou.
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
class OpcaoModelo:
    id: str
    rotulo: str
    habilitado: bool   # False = sem chave cadastrada (Opções → API Keys)


@dataclasses.dataclass
class Passo:
    titulo: str
    corpo: str = ""            # as linhas do passo num markdown só
    estado: str = ""           # "" | rodando | ok | erro | pulado


@dataclasses.dataclass
class Mensagem:
    papel: str                 # "user" | "assistant"
    texto: str = ""
    # Cartão do plano (vazio = mensagem comum)
    titulo: str = ""
    passos: list[Passo] = dataclasses.field(default_factory=list)
    multi: bool = False        # plano com mais de um passo (mostra cada título)
    aviso: str = ""
    botoes: list[Botao] = dataclasses.field(default_factory=list)
    estado: str = ""           # "" | pendente | rodando | feito | cancelado
    erro: bool = False


def _botoes(acoes) -> tuple[list[Botao], str]:
    """Botões do cartão + aviso, pelo checkpoint de cada passo (mesmas regras
    dos diálogos da página de Desmembramento e do início da Requisição)."""
    multi = len(acoes) > 1
    avisos = [(f"{a.titulo}: " if multi else "") + a.aviso for a in acoes if a.aviso]

    if any(a.checkpoint == "corrompido" for a in acoes):
        return [Botao("cancelar", *BOTOES["cancelar"])], (
            "O checkpoint de um passo existe mas está ilegível. Não vou rodar: "
            "poderia recriar chamados que já existem.")

    def e_req(a):
        return a.ferramenta == "criar_requisicoes"

    pendente = [a for a in acoes if a.checkpoint == "pendente"]
    concluido_desm = [a for a in acoes if a.checkpoint == "concluido" and not e_req(a)]
    concluido_req = [a for a in acoes if a.checkpoint == "concluido" and e_req(a)]

    cods: list[str] = []
    if not multi and concluido_req:
        cods = []  # lote já criado: só dá para fechar o cartão
    elif pendente:
        cods = ["retomar"]
        if any(not e_req(a) for a in pendente) or concluido_desm:
            cods.append("do_zero")
    elif concluido_desm:
        # Sozinho, "Confirmar" não faria nada (já concluído); num plano, roda
        # os outros passos e esse só relata.
        cods = (["confirmar"] if multi else []) + ["do_zero"]
    else:
        cods = ["confirmar"]

    escreve = any(a.escreve for a in acoes)
    if escreve and cods and all(a.pode_simular or not a.escreve for a in acoes):
        cods.append("simular")
    cods.append("cancelar")
    if pendente and any(not e_req(a) for a in pendente):
        avisos.insert(0, "Existe uma execução pela metade.")
    if concluido_desm:
        avisos.insert(0, "Já foi concluído antes.")
    return [Botao(c, *BOTOES[c]) for c in cods], " ".join(avisos)


class AssistenteState(rx.State):
    mensagens: list[Mensagem] = []
    entrada: str = ""
    pensando: bool = False
    status_pensando: str = "Pensando..."  # ou "Verificando o SLA..." etc.
    rodando: bool = False
    status_vivo: str = ""
    # Últimas linhas de log da execução em andamento, mostradas discretas
    # abaixo do passo que está rodando.
    logs_vivos: list[str] = []
    tem_chave: bool = False
    # Modelo de IA escolhido no seletor do chat (02/10) e as opções dele.
    modelo: str = "groq"
    modelos: list[OpcaoModelo] = []
    # False até o on_load consultar o Cofre. Sem isto a página desenhava a
    # caixa "cole a chave" por um instante e trocava pelo chat (bug de 30/09).
    chave_verificada: bool = False

    # Só no servidor (prefixo _): o histórico que vai para a IA e os planos
    # esperando clique, por índice da mensagem-cartão.
    _historico: list[dict] = []
    _planos: dict[int, list] = {}

    @rx.event
    def on_load(self):
        from services.agente import llm
        disponiveis = llm.disponiveis()
        self.tem_chave = bool(disponiveis)
        self.modelos = [OpcaoModelo(m.id, m.rotulo, m.id in disponiveis)
                        for m in llm.MODELOS.values()]
        self.modelo = llm.modelo_escolhido()
        self.chave_verificada = True

    @rx.event
    def set_entrada(self, v: str):
        self.entrada = v

    @rx.event
    def set_modelo(self, modelo_id: str):
        """Troca o modelo pelo seletor. Vale a partir do PRÓXIMO pedido (a
        conversa continua a mesma) e fica guardado para a próxima vez."""
        from services.agente import llm
        if not any(o.id == modelo_id and o.habilitado for o in self.modelos):
            return rx.toast.warning("Cadastre a chave desse modelo em Opções → API Keys.")
        llm.escolher_modelo(modelo_id)
        self.modelo = modelo_id

    @rx.event
    def nova_conversa(self):
        if self.rodando:
            return rx.toast.warning("Espere a execução atual terminar.")
        self.mensagens = []
        self._historico = []
        self._planos = {}

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
            modelo_id = self.modelo
            self.pensando = True
            self.status_pensando = "Pensando..."
        yield

        from services import credenciais
        from services.agente.assistente import responder
        from services.agente.llm import ErroLLM
        matricula, senha = credenciais.carregar()

        # Thread dedicada (não to_thread): o responder pode abrir o navegador
        # para INVESTIGAR (fila, SLA), e o Playwright sync se prende à thread.
        # `avisar` atualiza a linha "Procurando o chamado..." enquanto isso.
        loop = asyncio.get_running_loop()
        fila: asyncio.Queue = asyncio.Queue()

        def avisar(t):
            loop.call_soon_threadsafe(fila.put_nowait, ("aviso", t))

        def runner():
            try:
                saida = ("ok", responder(historico, matricula, senha, avisar, modelo_id))
            except Exception as e:
                saida = ("erro", e)
            loop.call_soon_threadsafe(fila.put_nowait, saida)

        threading.Thread(target=runner, daemon=True).start()
        while True:
            tipo, dado = await fila.get()
            if tipo == "aviso":
                async with self:
                    self.status_pensando = dado
                yield
                continue
            break
        try:
            if tipo == "erro":
                raise dado
            r = dado
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
            if not r.acoes:
                self.mensagens = self.mensagens + [Mensagem(papel="assistant", texto=r.texto)]
                self._historico = self._historico + [{"role": "assistant", "content": r.texto}]
                return
            escreve = any(a.escreve for a in r.acoes)
            botoes, aviso = _botoes(r.acoes)
            multi = len(r.acoes) > 1
            cartao = Mensagem(
                papel="assistant", texto=r.texto,
                titulo=f"Plano — {len(r.acoes)} passos" if multi else r.acoes[0].titulo,
                passos=[Passo(titulo=a.titulo, corpo="  \n".join(a.linhas)) for a in r.acoes],
                multi=multi, aviso=aviso,
                botoes=botoes if escreve else [],
                estado="pendente" if escreve else "rodando",
            )
            indice = len(self.mensagens)
            self.mensagens = self.mensagens + [cartao]
            self._planos = {**self._planos, indice: list(r.acoes)}
            nomes = ", ".join(a.titulo for a in r.acoes)
            nota = (f"[Mostrei o plano ({nomes}) para o técnico confirmar.]"
                    if escreve else f"[Executando: {nomes}.]")
            self._historico = self._historico + [{"role": "assistant", "content": nota}]
            if not escreve:
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
            acoes = self._planos.get(indice)
            if acoes is None or indice >= len(self.mensagens):
                return
            if botao == "cancelar":
                self._marcar(indice, estado="cancelado")
                self._historico = self._historico + [
                    {"role": "assistant", "content": "[O técnico cancelou o plano.]"}]
                self._planos = {k: v for k, v in self._planos.items() if k != indice}
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
            self._marcar(indice, estado="rodando")
            from services import credenciais
            matricula, senha = credenciais.carregar()
        yield

        if not matricula or not senha:
            async with self:
                self._encerrar(indice, acoes, [], "Credenciais não cadastradas "
                               "(Opções → Credenciais).")
            return

        loop = asyncio.get_running_loop()
        fila: asyncio.Queue = asyncio.Queue()

        def emitir(tipo, dado=None):
            loop.call_soon_threadsafe(fila.put_nowait, (tipo, dado))

        def log(m, tipo="info"):
            emitir("log", str(m))

        def runner():
            from services.agente.ferramentas import executar
            from services.agente.sessao import Sessao, executar_plano
            sessao = Sessao(matricula, senha, log, modo_teste=(botao == "simular"),
                            iniciar_do_zero=(botao == "do_zero"))
            executar_plano(acoes, sessao, executar, emitir)

        threading.Thread(target=runner, daemon=True).start()
        resultados: list = []
        while True:
            tipo, dado = await fila.get()
            async with self:
                if tipo == "log":
                    self.status_vivo = dado
                    self.logs_vivos = (self.logs_vivos + [dado])[-_LOGS_VISIVEIS:]
                elif tipo == "passo":
                    i, estado = dado
                    self._marcar_passo(indice, i, estado)
                    if estado == "rodando":
                        self.logs_vivos = []
                elif tipo == "resultado":
                    i, r = dado
                    resultados.append((acoes[i].titulo, r.ok))
                    self._marcar_passo(indice, i, "ok" if r.ok else "erro")
                    texto = r.texto
                    if not r.ok and self.logs_vivos:
                        # As linhas do log somem do cartão quando o passo acaba;
                        # na falha, ficam no resultado para dizer onde parou.
                        texto += ("\n\n*Últimas linhas do log:*\n"
                                  + "\n".join(f"- `{l}`" for l in self.logs_vivos))
                    self.mensagens = self.mensagens + [
                        Mensagem(papel="assistant", texto=texto, erro=not r.ok)]
                else:  # fim
                    self._encerrar(indice, acoes, resultados)
            yield
            if tipo == "fim":
                return

    def _marcar(self, indice: int, **campos):
        msgs = list(self.mensagens)
        msgs[indice] = dataclasses.replace(msgs[indice], **campos)
        self.mensagens = msgs

    def _marcar_passo(self, indice: int, i: int, estado: str):
        passos = list(self.mensagens[indice].passos)
        passos[i] = dataclasses.replace(passos[i], estado=estado)
        self._marcar(indice, passos=passos)

    def _encerrar(self, indice: int, acoes, resultados, erro_geral: str = ""):
        self._marcar(indice, estado="feito")
        if erro_geral:
            self.mensagens = self.mensagens + [
                Mensagem(papel="assistant", texto=erro_geral, erro=True)]
        # Nota curta para a IA — sem nada lido do Assyst (LGPD).
        if erro_geral:
            nota = f"[O plano não rodou: {erro_geral}]"
        else:
            feitos = ", ".join(f"{t} ({'ok' if ok else 'falhou'})" for t, ok in resultados)
            pulados = len(acoes) - len(resultados)
            nota = (f"[Plano executado: {feitos}"
                    + (f"; {pulados} passo(s) não rodaram por causa da falha" if pulados else "")
                    + ". O resultado foi mostrado ao técnico.]")
        self._historico = self._historico + [{"role": "assistant", "content": nota}]
        self._planos = {k: v for k, v in self._planos.items() if k != indice}
        self.rodando = False
        self.status_vivo = ""
        self.logs_vivos = []
