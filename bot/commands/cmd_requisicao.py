"""
bot/cmd_requisicao.py — /requisicao: abre UM chamado do zero, passo a passo.

Reescrito em 2026-08-27 (era colar um bloco `campo;campo;campo` por linha,
formato pensado pro desktop). No celular isso é ruim de digitar; agora o bot
PERGUNTA campo por campo, na ordem de `requisicao_campos.ORDEM_COLUNAS`, e
UM chamado por vez só — no celular não faz sentido colar 40 linhas de uma vez
como no formato antigo.

As opções de cada campo vêm do banco de referência (services/dados/
referencia.py; aba "Referência" de Configurações) desde 28/10 — antes eram os
"Presets" do SQLite. Lista curta (até _MAX_BOTOES) vira BOTÃO, sem digitar
por cima (decisão do usuário: se não tiver o valor certo, ajeita depois no
PC). Lista longa (edifícios, técnicos, filas) pede um pedaço do nome e
mostra como botão o que bater; nada batendo, aceita o texto digitado (a
lista de edifícios ainda é incompleta). Campo sem lista pede texto.
Usuário afetado e Descrição são SEMPRE digitados.

Campo opcional (tudo exceto Item) ganha botão "Pular" — obrigar a preencher
Item B/Categoria/Grupo/Usuário Atribuído toda vez seria fricção sem motivo.

O motor da automação NÃO mudou: `bot/requisicao_service.criar_lote` já
aceitava uma LISTA de dicts {campo: valor} — aqui só passamos uma lista de
um item só, montado pelas respostas do wizard em vez de parseado de um
texto colado.
"""
import asyncio
import os
import unicodedata

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.comum import WIZARD, liberado, log_bot, quem
from bot.services import credencial_servico, requisicao_service
from services.regras.requisicao_campos import ORDEM_COLUNAS, POR_CHAVE

# Preenche tudo e PARA antes de salvar. Mesmo padrao dos outros fluxos: flag
# de ambiente, nao botao — o app desktop nao expoe isto.
REQUISICAO_TESTE = os.getenv("BOT_REQUISICAO_TESTE") == "1"

# Até quantas opções a lista vira botão direto; acima disso, pede um pedaço
# do nome e filtra.
_MAX_BOTOES = 8

# Opcionais no Assyst (tudo exceto Item, que e obrigatorio) — ganham "Pular".
_PULAVEL = {"edificio", "resumo", "item_b", "categoria", "grupo_atribuido", "usuario_atribuido"}

_PERGUNTAS = {
    "usuario_afetado": "Qual a matrícula do usuário afetado?",
    "edificio": "Qual o Edifício?",
    "resumo": "Qual o Resumo?",
    "descricao": "Qual a Descrição?",
    "item": "Qual o Item?",
    "item_b": "Qual o Item B?",
    "categoria": "Qual a Categoria?",
    "grupo_atribuido": "Qual o Grupo de Serv. Atribuído?",
    "usuario_atribuido": "Qual o Usuário Atribuído?",
}


def _proximo_campo(atual: str) -> str | None:
    i = ORDEM_COLUNAS.index(atual)
    return ORDEM_COLUNAS[i + 1] if i + 1 < len(ORDEM_COLUNAS) else None


def _carregar_opcoes() -> dict[str, list[str]]:
    from services.dados import referencia
    return {
        "edificio": referencia.nomes_edificios(),
        "resumo": referencia.valores("resumo"),
        "item": referencia.valores("item"),
        "item_b": referencia.valores("item_b"),
        "categoria": referencia.valores("categoria"),
        "grupo_atribuido": referencia.filas(),
        "usuario_atribuido": referencia.tecnicos(),
    }


def _opcoes(estado, campo: str) -> list[str]:
    return estado["opcoes"].get(campo, [])


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                   if unicodedata.category(c) != "Mn")


def _filtrar(opcoes: list[str], texto: str) -> list[str]:
    """Opções que contêm todas as palavras digitadas (sem acento)."""
    palavras = _sem_acento(texto).split()
    return [o for o in opcoes if all(p in _sem_acento(o) for p in palavras)]


async def _enviar_pergunta(context, chat_id, estado, botoes=None, texto=None) -> None:
    """Pergunta o campo atual. `botoes` (as opções mostradas) ficam em
    estado["botoes"] — o índice do callback aponta para elas."""
    campo = estado["passo"]
    opcoes = _opcoes(estado, campo)
    if botoes is None:
        botoes = opcoes if len(opcoes) <= _MAX_BOTOES else []
    estado["botoes"] = botoes

    linhas_botoes = [[InlineKeyboardButton(v, callback_data=f"rq:v:{i}")]
                     for i, v in enumerate(botoes)]
    if campo in _PULAVEL:
        linhas_botoes.append([InlineKeyboardButton("⏭ Pular", callback_data="rq:pular")])
    teclado = InlineKeyboardMarkup(linhas_botoes) if linhas_botoes else None

    if texto is None:
        texto = _PERGUNTAS[campo]
        if len(opcoes) > _MAX_BOTOES:
            texto += " (digite parte do nome)"
        elif opcoes:
            texto += " (escolha um botão)"
    await context.bot.send_message(chat_id, texto, reply_markup=teclado)


async def _avancar(context, chat_id, estado) -> None:
    proximo = _proximo_campo(estado["passo"])
    if proximo is None:
        estado["passo"] = "confirmar"
        await _mostrar_confirmacao(context, chat_id, estado)
        return
    estado["passo"] = proximo
    await _enviar_pergunta(context, chat_id, estado)


async def _mostrar_confirmacao(context, chat_id, estado) -> None:
    valores = estado["valores"]
    linhas = []
    for campo in ORDEM_COLUNAS:
        valor = valores.get(campo, "")
        linhas.append(f"  {POR_CHAVE[campo].rotulo}: {valor or '(vazio)'}")

    aviso = "MODO TESTE — nada será salvo.\n\n" if REQUISICAO_TESTE else ""
    teclado = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Confirmar", callback_data="rq:ok"),
        InlineKeyboardButton("✖️ Cancelar", callback_data="rq:nao"),
    ]])
    await context.bot.send_message(
        chat_id,
        f"{aviso}Confere os dados?\n\n" + "\n".join(linhas) + "\n\nConfirma a criação?",
        reply_markup=teclado,
    )


async def cmd_requisicao(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not liberado(update):
        return

    estado = {
        "fluxo": "requisicao",
        "passo": ORDEM_COLUNAS[0],
        "valores": {},
        # Carregado uma vez no início da conversa — não muda no meio dela
        # mesmo que alguém edite a referência pelo app nesse meio-tempo.
        "opcoes": _carregar_opcoes(),
        "botoes": [],
    }
    WIZARD[chat_id] = estado
    await _enviar_pergunta(context, chat_id, estado)


async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Trata TEXTO digitado: valor de campo sem lista, ou o pedaço do nome
    que filtra uma lista longa. Lista curta só aceita botão."""
    chat_id = update.effective_chat.id
    estado = WIZARD[chat_id]
    campo = estado["passo"]

    if campo == "confirmar":
        return  # so os botoes de confirmar valem aqui

    opcoes = _opcoes(estado, campo)
    if 0 < len(opcoes) <= _MAX_BOTOES:
        await update.message.reply_text("Use os botões acima pra escolher (ou /cancelar).")
        return

    texto = update.message.text.strip()
    if not texto:
        await update.message.reply_text("Digite um valor.")
        return

    if opcoes:
        batem = _filtrar(opcoes, texto)
        if len(batem) > 1:
            extra = " Se não estiver aqui, digite mais do nome." if len(batem) > _MAX_BOTOES else ""
            await _enviar_pergunta(context, chat_id, estado, batem[:_MAX_BOTOES],
                                   f"Achei {len(batem)}. Escolha:{extra}")
            return
        if batem:
            texto = batem[0]
        else:
            await update.message.reply_text(
                f"'{texto}' não está na referência — vai assim mesmo.")

    await update.message.reply_text(f"{POR_CHAVE[campo].rotulo}: {texto}")
    estado["valores"][campo] = texto
    await _avancar(context, chat_id, estado)


async def escolher_valor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = query.message.chat_id
    await query.answer()
    if not liberado(update):
        return

    estado = WIZARD.get(chat_id)
    if not estado or estado.get("passo") == "confirmar":
        await query.edit_message_text("Esse pedido expirou. Mande /requisicao de novo.")
        return

    campo = estado["passo"]
    botoes = estado.get("botoes", [])
    idx = int(query.data.split(":")[2])
    if idx < 0 or idx >= len(botoes):
        await query.edit_message_text("Essa opção não vale mais. Mande /requisicao de novo.")
        return

    valor = botoes[idx]
    estado["valores"][campo] = valor
    await query.edit_message_text(f"{POR_CHAVE[campo].rotulo}: {valor}")
    await _avancar(context, chat_id, estado)


async def pular(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = query.message.chat_id
    await query.answer()
    if not liberado(update):
        return

    estado = WIZARD.get(chat_id)
    if not estado or estado.get("passo") == "confirmar":
        await query.edit_message_text("Esse pedido expirou. Mande /requisicao de novo.")
        return

    campo = estado["passo"]
    if campo not in _PULAVEL:
        return

    estado["valores"][campo] = ""
    await query.edit_message_text(f"{POR_CHAVE[campo].rotulo}: (pulado)")
    await _avancar(context, chat_id, estado)


async def confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = query.message.chat_id
    await query.answer()
    if not liberado(update):
        return

    estado = WIZARD.pop(chat_id, None)
    if not estado or estado.get("passo") != "confirmar":
        await query.edit_message_text("Esse pedido expirou. Mande /requisicao de novo.")
        return

    if query.data == "rq:nao":
        await query.edit_message_text("Cancelado. Nada foi criado.")
        return

    matricula, senha = credencial_servico.carregar_de(chat_id)
    if not senha:
        await query.edit_message_text(
            "Você ainda não cadastrou sua credencial do Assyst. Mande "
            "/credencial primeiro."
        )
        return

    # Igual ao parse do formato antigo: campo vazio/pulado NAO entra no dict
    # ("nao mexer", nunca "apagar") — ver services/fluxos/flow_requisicao_pw.parse_linha.
    valores = {k: v for k, v in estado["valores"].items() if v}

    await query.edit_message_text("▶️ Criando a requisição...")

    autor = quem(update)

    def log(msg, tipo="info"):
        log_bot.info("[%s] %s", autor, msg)

    try:
        resultados = await asyncio.to_thread(
            requisicao_service.criar_lote,
            [valores], matricula, senha, log, REQUISICAO_TESTE,
        )
    except Exception as e:
        log_bot.exception("Falha na requisicao de %s", matricula)
        await context.bot.send_message(chat_id, f"❌ A automação quebrou: {e}")
        return

    r = resultados[0]
    if r["ok"]:
        numero = r["numero"] or "(modo teste, sem número)"
        texto = f"🟢 Chamado criado: {numero} · {r['usuario']}"
    else:
        texto = f"❌ Não criou: {r['erro']} · {r['usuario']}"
    if REQUISICAO_TESTE:
        texto += "\n\n⚠️ MODO TESTE: nada foi salvo no Assyst."
    await context.bot.send_message(chat_id, texto)
