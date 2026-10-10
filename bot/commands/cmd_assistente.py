"""
bot/commands/cmd_assistente.py — O Assistente (IA) no Telegram (10/10).

Mesmo agente do chat do app (services/agente): o texto solto que não é
resposta de um comando (/sla, /requisicao...) vai para a IA, que monta o
plano; plano que ESCREVE vira cartão com botões (Confirmar / Simular /
Cancelar), o que só lê roda direto. As regras do cartão são as mesmas do app
(services/agente/cartao.py) — aqui só se traduz para mensagem e botões.

Comandos:
  /chave  — cadastra a chave de IA do técnico (cada um a sua; apagada da
            conversa assim que lida, como a senha do /credencial)
  /modelo — escolhe o modelo entre os que têm chave
  /nova   — começa uma conversa nova (esquece o histórico)

Credencial do Assyst = a do /credencial de quem pediu. Conversa e planos em
MEMÓRIA, por chat_id: não sobrevivem a um restart do bot, de propósito
(mesmo critério do WIZARD em bot/comum.py).

Com `python -m bot.main --teste`, Confirmar roda como SIMULAÇÃO: nada é
salvo no Assyst.
"""
import asyncio
import dataclasses
import html
import itertools
import os
import re
import threading

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.comum import WIZARD, liberado, log_bot, quem
from bot.services import chave_ia_servico, credencial_servico

TESTE = os.getenv("BOT_ASSISTENTE_TESTE") == "1"

# Mensagens guardadas por conversa (pedidos + notas). Mais que isso, as mais
# antigas saem: cada ida à IA reenvia o histórico inteiro (tokens).
_MAX_HISTORICO = 40


@dataclasses.dataclass
class _Conversa:
    historico: list[dict] = dataclasses.field(default_factory=list)
    planos: dict[int, list] = dataclasses.field(default_factory=dict)   # id -> ações
    registros: dict[int, "int | None"] = dataclasses.field(default_factory=dict)
    ocupado: bool = False   # pensando ou executando: um pedido por vez


_CONVERSAS: dict[int, _Conversa] = {}
_IDS = itertools.count(1)


def _conversa(chat_id) -> _Conversa:
    return _CONVERSAS.setdefault(chat_id, _Conversa())


def _guardar(c: _Conversa, papel: str, texto: str) -> None:
    c.historico = (c.historico + [{"role": papel, "content": texto}])[-_MAX_HISTORICO:]


# --------------------------------------------------------------------------- #
# Texto: markdown do agente -> HTML do Telegram
# --------------------------------------------------------------------------- #

def _html(md: str, limite: int = 3800) -> str:
    """O agente escreve em markdown (**negrito**, *itálico*, `código`); o
    Telegram aceita HTML com poucas tags. Corta ANTES de converter, para
    nunca partir uma tag ao meio (limite do Telegram: 4096)."""
    md = (md or "").strip()
    if len(md) > limite:
        md = md[:limite].rstrip() + "…"
    t = html.escape(md, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t, flags=re.S)
    t = re.sub(r"(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])", r"<i>\1</i>", t)
    t = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", t)
    return t.replace("  \n", "\n")


def _no_bot(texto: str) -> str:
    """As mensagens de erro da IA falam da tela do app; aqui os caminhos são
    comandos."""
    return (texto.replace("Opções → API Keys", "/chave")
            .replace("troque o modelo no seletor do chat", "troque o modelo com /modelo")
            .replace("Troque o modelo no seletor do chat", "Troque o modelo com /modelo"))


async def _mandar(context, chat_id, md: str, teclado=None, editar=None):
    """Envia (ou edita `editar`) em HTML; se o Telegram recusar o HTML,
    manda o texto puro — a mensagem nunca se perde por formatação."""
    for texto, modo in ((_html(md), ParseMode.HTML), ((md or "…")[:3900], None)):
        try:
            if editar is not None:
                return await editar.edit_text(texto, parse_mode=modo, reply_markup=teclado)
            return await context.bot.send_message(chat_id, texto, parse_mode=modo,
                                                  reply_markup=teclado)
        except Exception as e:
            if modo is None:
                log_bot.warning("Assistente: não consegui enviar a mensagem: %s", e)
    return None


class _Status:
    """A linha "⏳ ..." que acompanha o pedido. `avisar` é chamado da thread
    do agente; o laço (no loop do bot) edita a mensagem no máximo a cada
    1,5 s — o Telegram limita edições."""

    def __init__(self, msg):
        self.msg, self.texto, self.mostrado = msg, "", ""

    def avisar(self, texto, *_):
        self.texto = str(texto)

    async def laco(self):
        while True:
            await asyncio.sleep(1.5)
            if self.texto and self.texto != self.mostrado:
                self.mostrado = self.texto
                try:
                    await self.msg.edit_text(f"⏳ {self.texto[:300]}")
                except Exception:
                    pass


# --------------------------------------------------------------------------- #
# Pedido -> resposta ou cartão
# --------------------------------------------------------------------------- #

def _rotulo(codigo: str) -> str:
    from services.agente import cartao
    r = cartao.ROTULOS[codigo]
    return f"{r} (modo teste)" if TESTE and codigo in ("confirmar", "retomar", "do_zero") else r


def _cartao_md(r, aviso: str) -> str:
    multi = len(r.acoes) > 1
    partes = [f"**{'Plano — %d passos' % len(r.acoes) if multi else r.acoes[0].titulo}**"]
    if r.texto:
        partes.append(r.texto)
    for i, a in enumerate(r.acoes, 1):
        corpo = "\n".join(l.replace("  \n", "\n") for l in a.linhas)
        partes.append(f"**{i}. {a.titulo}**\n{corpo}" if multi else corpo)
    if aviso:
        partes.append(f"⚠️ {aviso}")
    if TESTE and any(a.escreve for a in r.acoes):
        partes.append("🧪 Bot em modo teste: nada será salvo no Assyst.")
    return "\n\n".join(partes)


async def conversar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Texto solto -> Assistente."""
    from services.agente import cartao, registro
    from services.agente.assistente import responder
    from services.agente.llm import ErroLLM

    chat_id = update.effective_chat.id
    texto = (update.message.text or "").strip()
    if not texto:
        return
    c = _conversa(chat_id)
    if c.ocupado:
        await update.message.reply_text("Ainda estou no pedido anterior — espere terminar.")
        return
    matricula, senha = credencial_servico.carregar_de(chat_id)
    if not matricula:
        await update.message.reply_text(
            "Antes de usar o Assistente, cadastre sua credencial do Assyst com /credencial.")
        return
    modelo_id, chave = chave_ia_servico.escolhido_de(chat_id)
    if not chave:
        await update.message.reply_text(
            "Antes de usar o Assistente, cadastre sua chave de IA com /chave "
            "(cada técnico usa a sua).")
        return

    _guardar(c, "user", texto)
    c.ocupado = True
    status = await update.message.reply_text("⏳ Pensando...")
    st = _Status(status)
    tarefa = asyncio.create_task(st.laco())
    try:
        # Thread única para o pedido inteiro: o agente pode abrir o navegador
        # para investigar (fila, SLA) e o Playwright sync se prende à thread.
        r = await asyncio.to_thread(responder, list(c.historico), matricula, senha,
                                    st.avisar, modelo_id, chave)
    except ErroLLM as e:
        registro.gravar_pedido(matricula, modelo_id, texto, desfecho="erro", erro=str(e))
        await _mandar(context, chat_id, "❌ " + _no_bot(str(e)), editar=status)
        return
    except Exception as e:
        log_bot.exception("Assistente: erro inesperado (%s)", quem(update))
        registro.gravar_pedido(matricula, modelo_id, texto, desfecho="erro",
                               erro=f"inesperado: {e}")
        await _mandar(context, chat_id, f"❌ Erro inesperado: {e}", editar=status)
        return
    finally:
        tarefa.cancel()
        c.ocupado = False

    escreve = any(a.escreve for a in r.acoes)
    id_reg = registro.gravar_pedido(
        matricula, modelo_id, texto, r,
        desfecho="resposta" if not r.acoes else ("pendente" if escreve else "executou"))
    ja = cartao.nota_lembrar(r.lembrar)
    if not r.acoes:
        _guardar(c, "assistant", r.texto + ja)
        await _mandar(context, chat_id, r.texto or "…", editar=status)
        return

    pid = next(_IDS)
    c.planos[pid], c.registros[pid] = list(r.acoes), id_reg
    _guardar(c, "assistant", cartao.nota_plano(r.acoes, escreve) + ja)
    cods, aviso = cartao.botoes(r.acoes)
    teclado = None
    if escreve:
        teclado = InlineKeyboardMarkup(
            [[InlineKeyboardButton(_rotulo(cod), callback_data=f"ag:{pid}:{cod}")]
             for cod in cods])
    await _mandar(context, chat_id, _cartao_md(r, aviso), teclado, editar=status)
    if not escreve:
        await _executar(context, chat_id, pid, "auto")


# --------------------------------------------------------------------------- #
# Botões do cartão -> execução
# --------------------------------------------------------------------------- #

async def acionar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback `ag:<plano>:<botão>`."""
    from services.agente import cartao, registro

    q = update.callback_query
    if not liberado(update):
        await q.answer()
        return
    chat_id = update.effective_chat.id
    _, pid, botao = q.data.split(":")
    pid = int(pid)
    c = _conversa(chat_id)
    if pid not in c.planos:
        await q.answer("Esse cartão já foi usado.")
        try:
            await q.edit_message_reply_markup(None)
        except Exception:
            pass
        return
    if c.ocupado and botao != "cancelar":
        await q.answer("Já tem um pedido em andamento.")
        return
    await q.answer()
    try:
        await q.edit_message_reply_markup(None)  # o cartão não roda duas vezes
    except Exception:
        pass
    if botao == "cancelar":
        registro.marcar_desfecho(c.registros.pop(pid, None), "cancelou")
        c.planos.pop(pid, None)
        _guardar(c, "assistant", "[O técnico cancelou o plano.]")
        await context.bot.send_message(chat_id, "Cancelado.")
        return
    if botao in cartao.DESFECHO:
        registro.marcar_desfecho(c.registros.get(pid), cartao.DESFECHO[botao])
    await _executar(context, chat_id, pid, botao)


async def _executar(context, chat_id, pid: int, botao: str) -> None:
    from services.agente import cartao, registro

    c = _conversa(chat_id)
    acoes = c.planos.pop(pid)
    id_reg = c.registros.pop(pid, None)
    matricula, senha = credencial_servico.carregar_de(chat_id)
    no_assyst = cartao.usa_assyst(acoes)
    if no_assyst and not (matricula and senha):
        erro = "Credencial do Assyst não cadastrada (/credencial)."
        registro.gravar_resultado(id_reg, [], erro)
        _guardar(c, "assistant", cartao.nota_fim(acoes, [], erro))
        await context.bot.send_message(chat_id, f"❌ {erro}")
        return
    simular = botao == "simular" or (TESTE and any(a.escreve for a in acoes))

    c.ocupado = True
    status = await context.bot.send_message(
        chat_id, "⏳ Abrindo o navegador..." if no_assyst else "⏳ Gerando...")
    st = _Status(status)
    tarefa = asyncio.create_task(st.laco())
    loop = asyncio.get_running_loop()
    fila: asyncio.Queue = asyncio.Queue()

    def emitir(tipo, dado=None):
        loop.call_soon_threadsafe(fila.put_nowait, (tipo, dado))

    def rodar():
        # Thread dedicada (não to_thread): Sessao criada, usada e fechada na
        # MESMA thread — o Playwright sync se prende a ela.
        from services.agente.ferramentas import executar
        from services.agente.sessao import Sessao, executar_plano
        try:
            sessao = Sessao(matricula, senha, st.avisar, modo_teste=simular,
                            iniciar_do_zero=(botao == "do_zero"))
            executar_plano(acoes, sessao, executar, emitir)
        except Exception as e:  # executar_plano sempre emite "fim"; isto é antes dele
            emitir("erro", str(e))
            emitir("fim")

    threading.Thread(target=rodar, daemon=True).start()
    resultados: list[tuple[str, bool, str]] = []
    erro_geral = ""
    try:
        while True:
            tipo, dado = await fila.get()
            if tipo == "fim":
                break
            if tipo == "erro":
                erro_geral = dado
            elif tipo == "passo" and dado[1] == "rodando" and len(acoes) > 1:
                st.avisar(f"Passo {dado[0] + 1} de {len(acoes)}: {acoes[dado[0]].titulo}...")
            elif tipo == "resultado":
                i, r = dado
                resultados.append((acoes[i].titulo, r.ok, r.texto))
                await _mandar(context, chat_id, r.texto)
                for arq in r.arquivos:
                    try:
                        with open(arq, "rb") as f:
                            await context.bot.send_document(chat_id, f,
                                                            filename=os.path.basename(arq))
                    except Exception as e:
                        log_bot.warning("Assistente: não consegui enviar %s: %s", arq, e)
                        await context.bot.send_message(
                            chat_id, f"⚠️ Não consegui enviar o arquivo {os.path.basename(arq)}.")
    finally:
        tarefa.cancel()
        c.ocupado = False
        try:
            await status.delete()
        except Exception:
            pass

    if erro_geral:
        await context.bot.send_message(chat_id, f"❌ {erro_geral}")
    pulados = len(acoes) - len(resultados)
    if pulados and resultados:
        await context.bot.send_message(
            chat_id, f"{pulados} passo(s) não rodaram por causa da falha acima.")
    registro.gravar_resultado(
        id_reg, [{"passo": t, "ok": ok, "texto": txt} for t, ok, txt in resultados], erro_geral)
    _guardar(c, "assistant", cartao.nota_fim(acoes, resultados, erro_geral))


# --------------------------------------------------------------------------- #
# /nova, /chave, /modelo
# --------------------------------------------------------------------------- #

async def cmd_nova(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not liberado(update):
        return
    chat_id = update.effective_chat.id
    if _conversa(chat_id).ocupado:
        await update.message.reply_text("Espere o pedido atual terminar.")
        return
    _CONVERSAS.pop(chat_id, None)
    await update.message.reply_text("Conversa nova. Pode pedir.")


async def cmd_chave(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from services.agente import llm
    if not liberado(update):
        return
    chat_id = update.effective_chat.id
    linhas = []
    for p in llm.PLATAFORMAS.values():
        tem = "✅ cadastrada" if chave_ia_servico.carregar_de(chat_id, p.id) else "— sem chave"
        linhas.append(f"{p.nome}: {tem}")
    teclado = InlineKeyboardMarkup([[InlineKeyboardButton(p.nome, callback_data=f"agk:{p.id}")]
                                    for p in llm.PLATAFORMAS.values()])
    await update.message.reply_text(
        "Sua chave de IA (cada técnico usa a sua):\n" + "\n".join(linhas)
        + "\n\nDe qual plataforma é a chave que vai cadastrar?", reply_markup=teclado)


async def escolher_plataforma(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback `agk:<plataforma>`."""
    from services.agente import llm
    q = update.callback_query
    await q.answer()
    if not liberado(update):
        return
    p = llm.PLATAFORMAS.get(q.data.split(":", 1)[1])
    if p is None:
        return
    WIZARD[update.effective_chat.id] = {"fluxo": "chave", "passo": "chave", "plataforma": p.id}
    aviso = f"\n\n{p.aviso}" if p.aviso else ""
    await q.edit_message_text(
        f"Cole sua chave da {p.nome} ({p.placeholder}).\nCrie em {p.link}{aviso}\n\n"
        "⚠️ Assim que eu ler, apago a mensagem — não fica na conversa.\n(/cancelar para desistir)")


async def responder_chave(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Wizard 'chave' (registrado no bot/main.py)."""
    from services.agente import llm
    chat_id = update.effective_chat.id
    estado = WIZARD.pop(chat_id, {})
    plataforma = estado.get("plataforma", "")
    try:
        await context.bot.delete_message(chat_id, update.message.message_id)
    except Exception:
        log_bot.warning("Não consegui apagar a mensagem com a chave de IA (chat_id=%s).", chat_id)
    try:
        chave_ia_servico.salvar_de(chat_id, plataforma, update.message.text or "")
    except ValueError as e:
        await context.bot.send_message(chat_id, f"❌ {e} Mande /chave de novo.")
        return
    nome = llm.PLATAFORMAS[plataforma].nome
    log_bot.info("[%s] cadastrou a própria chave de IA (%s)", quem(update), nome)
    await context.bot.send_message(
        chat_id, f"✅ Chave da {nome} salva — a mensagem com ela foi apagada. "
                 "Agora é só escrever o pedido.")


async def cmd_modelo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from services.agente import llm
    if not liberado(update):
        return
    chat_id = update.effective_chat.id
    ok = chave_ia_servico.disponiveis_de(chat_id)
    if not ok:
        await update.message.reply_text("Você ainda não tem chave de IA. Cadastre com /chave.")
        return
    atual, _ = chave_ia_servico.escolhido_de(chat_id)
    teclado = InlineKeyboardMarkup([[InlineKeyboardButton(
        ("● " if m == atual else "") + llm.MODELOS[m].rotulo, callback_data=f"agm:{m}")]
        for m in ok])
    await update.message.reply_text("Qual modelo de IA usar?", reply_markup=teclado)


async def escolher_modelo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback `agm:<modelo>`."""
    from services.agente import llm
    q = update.callback_query
    await q.answer()
    if not liberado(update):
        return
    modelo = q.data.split(":", 1)[1]
    if modelo not in chave_ia_servico.disponiveis_de(update.effective_chat.id):
        await q.edit_message_text("Esse modelo não tem chave. Cadastre com /chave.")
        return
    chave_ia_servico.escolher_de(update.effective_chat.id, modelo)
    await q.edit_message_text(f"✅ Usando {llm.MODELOS[modelo].rotulo}.")
