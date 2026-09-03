"""
bot/cmd_usuario.py — /infousuario: registra 'Aguardando Info do Usuário *'
em varios chamados.

So existe no bot: nao ha tela no app desktop para isto (ver
services/flow_usuario_pw.py). Irmao do /informacao e do /fornecedor — mesma
wizard, mesma execucao imediata com o MESMO texto pra todos os chamados da
lista; só muda o botao clicado no Assyst (Ações de relógio -> Aguardando
Info do Usuário *).
"""
import asyncio
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.comum import MAX_CHAMADOS, WIZARD, liberado, log_bot, quem
from bot.services import credencial_servico, usuario_service

# Preenche tudo e PARA antes de salvar. Mesmo padrao do FORNECEDOR_TESTE: flag
# de ambiente, nao botao — o app desktop nao expoe isto.
USUARIO_TESTE = os.getenv("BOT_USUARIO_TESTE") == "1"


def _parse_chamados(texto: str) -> list[str]:
    """Aceita numeros separados por linha OU por virgula, misturados."""
    brutos = texto.replace(",", "\n").splitlines()
    return [c.strip() for c in brutos if c.strip()]


async def cmd_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not liberado(update):
        return

    WIZARD[chat_id] = {"fluxo": "usuario", "passo": "chamados"}
    aviso = "\n\n⚠️ MODO TESTE ligado: nada será salvo." if USUARIO_TESTE else ""
    await update.message.reply_text(
        "Quais chamados? Um por linha ou separados por vírgula.\n"
        f"(até {MAX_CHAMADOS} de uma vez)"
        f"{aviso}\n\n(/cancelar para desistir)"
    )


async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    estado = WIZARD[chat_id]
    texto = update.message.text.strip()

    if estado["passo"] == "chamados":
        chamados = _parse_chamados(texto)
        if not chamados:
            await update.message.reply_text("Não entendi nenhum número. Tente de novo.")
            return
        if len(chamados) > MAX_CHAMADOS:
            await update.message.reply_text(
                f"São {len(chamados)} chamados; o limite é {MAX_CHAMADOS} por vez."
            )
            return

        estado["chamados"] = chamados
        estado["passo"] = "texto"
        lista = "\n".join(f"  • {c}" for c in chamados)
        await update.message.reply_text(
            f"{len(chamados)} chamado(s):\n{lista}\n\n"
            "Qual o texto a adicionar? (vale para todos)"
        )
        return

    if estado["passo"] == "texto":
        if not texto:
            await update.message.reply_text("O texto não pode ficar vazio. Digite algo.")
            return

        estado["texto"] = texto
        estado["passo"] = "confirmar"

        chamados = estado["chamados"]
        lista = "\n".join(f"  • {c}" for c in chamados)
        aviso = (
            "MODO TESTE — nada será salvo.\n\n" if USUARIO_TESTE
            else f"⚠️ Isto marca 'Aguardando Info do Usuário *' com o texto "
                 f"abaixo em {len(chamados)} chamado(s).\n\n"
        )
        teclado = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Confirmar", callback_data="us:ok"),
            InlineKeyboardButton("✖️ Cancelar", callback_data="us:nao"),
        ]])
        await update.message.reply_text(
            f"{aviso}Chamados:\n{lista}\n\nTexto:\n{texto}\n\nConfirma?",
            reply_markup=teclado,
        )
        return


async def confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = query.message.chat_id
    await query.answer()
    if not liberado(update):
        return

    estado = WIZARD.pop(chat_id, None)
    if not estado or estado.get("passo") != "confirmar":
        await query.edit_message_text("Esse pedido expirou. Mande /infousuario de novo.")
        return

    if query.data == "us:nao":
        await query.edit_message_text("Cancelado. Nada foi adicionado.")
        return

    matricula, senha = credencial_servico.carregar_de(chat_id)
    if not senha:
        await query.edit_message_text(
            "Você ainda não cadastrou sua credencial do Assyst. Mande "
            "/credencial primeiro."
        )
        return

    chamados = estado["chamados"]
    texto = estado["texto"]
    await query.edit_message_text(
        f"▶️ Registrando 'Aguardando Info do Usuário *' em {len(chamados)} chamado(s)..."
    )

    autor = quem(update)

    def log(msg, tipo="info"):
        log_bot.info("[%s] %s", autor, msg)

    try:
        resultados = await asyncio.to_thread(
            usuario_service.aguardar_lote,
            chamados, texto, matricula, senha, log, USUARIO_TESTE,
        )
    except Exception as e:
        log_bot.exception("Falha no infousuario de %s", matricula)
        await context.bot.send_message(chat_id, f"❌ A automação quebrou: {e}")
        return

    linhas = []
    for numero in chamados:
        ok, detalhe = resultados.get(numero, (False, "sem resultado"))
        if ok:
            linhas.append(f"✅ {numero}")
        else:
            linhas.append(f"❌ {numero} — {detalhe or 'falhou'}")
    if USUARIO_TESTE:
        linhas.append("\n⚠️ MODO TESTE: nada foi salvo no Assyst.")
    await context.bot.send_message(chat_id, "\n".join(linhas))
