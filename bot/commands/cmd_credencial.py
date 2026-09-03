"""
bot/cmd_credencial.py — /credencial: cada pessoa cadastra a PRÓPRIA matrícula
e senha do Assyst, usada pelo bot quando ELA pede uma ação.

Cadastro único: depois de mandar /credencial uma vez, /informacao,
/fornecedor, /atendimento etc. já usam essa credencial sozinhos — não precisa
repetir a cada fluxo. Só precisa mandar de novo se a senha mudar.

A senha é apagada da conversa assim que lida (ver `_apagar_com_cuidado`): fica
só um instante no histórico do Telegram, não para sempre.
"""
from telegram import Update
from telegram.ext import ContextTypes

from bot.comum import WIZARD, liberado, log_bot, quem
from bot.services import credencial_servico


async def _apagar_com_cuidado(context, chat_id, message_id) -> None:
    try:
        await context.bot.delete_message(chat_id, message_id)
    except Exception:
        # Nao e critico — a credencial ja foi salva. So avisa no log pra
        # saber que a mensagem com a senha ficou no historico da pessoa.
        log_bot.warning(
            "Nao consegui apagar a mensagem com a senha (chat_id=%s).", chat_id
        )


async def cmd_credencial(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not liberado(update):
        return

    ja_tem = credencial_servico.configurada_de(chat_id)
    aviso = (
        "\n\nVocê já tem uma cadastrada — mandar de novo substitui."
        if ja_tem else ""
    )
    WIZARD[chat_id] = {"fluxo": "credencial", "passo": "matricula"}
    await update.message.reply_text(
        "Vamos cadastrar sua credencial do Assyst — ela fica guardada no "
        "Cofre do Windows da máquina que roda o bot, e é usada só quando "
        "VOCÊ pedir uma ação.\n\n"
        "Qual sua matrícula?"
        f"{aviso}\n\n(/cancelar para desistir)"
    )


async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    estado = WIZARD[chat_id]
    texto = update.message.text.strip()

    if estado["passo"] == "matricula":
        if not texto:
            await update.message.reply_text("Digite sua matrícula.")
            return
        estado["matricula"] = texto
        estado["passo"] = "senha"
        await update.message.reply_text(
            "Agora sua senha do Assyst.\n\n"
            "⚠️ Assim que eu ler, apago esta mensagem — não fica salva na "
            "conversa."
        )
        return

    if estado["passo"] == "senha":
        if not texto:
            await update.message.reply_text("Digite sua senha.")
            return

        matricula = estado["matricula"]
        message_id = update.message.message_id
        WIZARD.pop(chat_id, None)

        try:
            credencial_servico.salvar_de(chat_id, matricula, texto)
        except Exception as e:
            log_bot.exception("Falha ao salvar credencial de %s", quem(update))
            await _apagar_com_cuidado(context, chat_id, message_id)
            await context.bot.send_message(chat_id, f"❌ Não consegui salvar: {e}")
            return

        await _apagar_com_cuidado(context, chat_id, message_id)
        log_bot.info("[%s] cadastrou a própria credencial (matrícula %s)", quem(update), matricula)
        await context.bot.send_message(
            chat_id,
            f"✅ Credencial salva (matrícula {matricula}). Sua senha foi "
            "apagada desta conversa.",
        )
        return
