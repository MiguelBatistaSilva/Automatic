"""
bot/cmd_requisicao.py — /requisicao: abre UM chamado do zero, passo a passo.

Reescrito em 2026-08-27 (era colar um bloco `campo;campo;campo` por linha,
formato pensado pro desktop). No celular isso é ruim de digitar; agora o bot
PERGUNTA campo por campo, na ordem de `requisicao_campos.ORDEM_COLUNAS`, e
UM chamado por vez só — no celular não faz sentido colar 40 linhas de uma vez
como no formato antigo.

Campo com valores pré-cadastrados (`services/requisicao_presets.py`, tela
"Presets da Requisição" no app) vira BOTÃO — sem opção de digitar por cima,
decisão do usuário (se não tiver o valor certo, ajeita depois no PC). Campo
SEM preset cadastrado pede texto digitado. Usuário afetado e Descrição são
SEMPRE digitados — mudam a cada chamado, não faz sentido pré-cadastrar.

Campo opcional (tudo exceto Item) ganha botão "Pular" — obrigar a preencher
Item B/Categoria/Grupo/Usuário Atribuído toda vez seria fricção sem motivo.

O motor da automação NÃO mudou: `bot/requisicao_service.criar_lote` já
aceitava uma LISTA de dicts {campo: valor} — aqui só passamos uma lista de
um item só, montado pelas respostas do wizard em vez de parseado de um
texto colado.
"""
import asyncio
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.comum import WIZARD, liberado, log_bot, quem
from bot.services import credencial_servico, requisicao_service
from services.requisicao_campos import ORDEM_COLUNAS, POR_CHAVE

# Preenche tudo e PARA antes de salvar. Mesmo padrao dos outros fluxos: flag
# de ambiente, nao botao — o app desktop nao expoe isto.
REQUISICAO_TESTE = os.getenv("BOT_REQUISICAO_TESTE") == "1"

# Sempre digitados: mudam a cada chamado, pre-cadastrar nao faz sentido.
_SEM_PRESET = {"usuario_afetado", "descricao"}

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


def _opcoes(estado, campo: str) -> list[str]:
    if campo in _SEM_PRESET:
        return []
    return estado["presets"].get(campo, [])


async def _enviar_pergunta(context, chat_id, estado) -> None:
    campo = estado["passo"]
    opcoes = _opcoes(estado, campo)

    linhas_botoes = [[InlineKeyboardButton(v, callback_data=f"rq:v:{i}")]
                     for i, v in enumerate(opcoes)]
    if campo in _PULAVEL:
        linhas_botoes.append([InlineKeyboardButton("⏭ Pular", callback_data="rq:pular")])
    teclado = InlineKeyboardMarkup(linhas_botoes) if linhas_botoes else None

    texto = _PERGUNTAS[campo]
    if opcoes:
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

    from services import requisicao_presets

    estado = {
        "fluxo": "requisicao",
        "passo": ORDEM_COLUNAS[0],
        "valores": {},
        # Carregado uma vez no início da conversa — não muda no meio dela
        # mesmo que alguém edite os presets pelo app nesse meio-tempo.
        "presets": requisicao_presets.carregar(),
    }
    WIZARD[chat_id] = estado
    await _enviar_pergunta(context, chat_id, estado)


async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Trata TEXTO digitado. Só serve pra campo sem preset — campo com preset
    só aceita botão (ver `escolher_valor`/`pular`)."""
    chat_id = update.effective_chat.id
    estado = WIZARD[chat_id]
    campo = estado["passo"]

    if campo == "confirmar":
        return  # so os botoes de confirmar valem aqui

    if _opcoes(estado, campo):
        await update.message.reply_text("Use os botões acima pra escolher (ou /cancelar).")
        return

    texto = update.message.text.strip()
    if not texto:
        await update.message.reply_text("Digite um valor.")
        return

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
    opcoes = _opcoes(estado, campo)
    idx = int(query.data.split(":")[2])
    if idx < 0 or idx >= len(opcoes):
        await query.edit_message_text("Essa opção não vale mais. Mande /requisicao de novo.")
        return

    valor = opcoes[idx]
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
    # ("nao mexer", nunca "apagar") — ver services/flow_requisicao_pw.parse_linha.
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
