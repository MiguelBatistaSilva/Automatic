"""
bot/main.py — a entrada do bot do Telegram.

Desde 05/11 o bot é só o Assistente: o técnico escreve o pedido, sem comando. Os
comandos que sobraram são de configuração:
    bot/commands/cmd_credencial.py      /credencial
    bot/commands/cmd_assistente.py      texto solto (Assistente/IA), /chave, /modelo, /nova

Este arquivo NAO tem regra de fluxo. Ele so le o token do Cofre do Windows, diz
quais comandos existem e encaminha o texto solto.

Desde 2026-08-26 a credencial do Assyst NAO e mais unica: cada chat_id loga
com a PROPRIA matricula/senha (ver bot/services/credencial_servico.py).

Quem liga normalmente é a tela do Assistente (services/bot_processo.py). Rodar à mão:
    python -m bot.main             producao — tudo vale
    python -m bot.main --teste     o Assistente nao salva nada no Assyst
"""
import os
import sys

# Este bloco vem ANTES dos imports do projeto de proposito: o bot/comum.py le
# estas variaveis no momento em que e importado, entao definir depois nao teria
# efeito nenhum. Flag de linha de comando em vez de variavel de ambiente porque
# a sintaxe de variavel muda conforme o terminal (PowerShell, CMD, Bash) e isso
# ja causou confusao.
if "--teste" in sys.argv:
    os.environ["BOT_ASSISTENTE_TESTE"] = "1"

from telegram import Update  # noqa: E402
from telegram.ext import (  # noqa: E402
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.commands import cmd_assistente, cmd_credencial  # noqa: E402
from bot.services import credencial_servico  # noqa: E402
from bot.comum import WIZARD, liberado, log_bot  # noqa: E402
from services.agente import agendados  # noqa: E402
from services.bot_processo import morrer_com_o_pai  # noqa: E402


# ---------------------------------------------------------------- /start

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not liberado(update):
        return

    aviso = "⚠️ MODO TESTE — nada será salvo no Assyst.\n\n" if cmd_assistente.TESTE else ""
    await update.message.reply_text(
        f"{aviso}"
        "Automatic — 2N CATI\n"
        "\n"
        "Escreva o pedido normalmente, sem comando — ex.: \"resolve o chamado "
        "da Carla, troquei o teclado\".\n"
        "\n"
        "CONFIGURAÇÃO\n"
        "/credencial — cadastra sua matrícula/senha do Assyst (uma vez só)\n"
        "/chave — cadastra sua chave de IA (uma vez só)\n"
        "/modelo — escolhe o modelo de IA\n"
        "\n"
        "/nova — começa uma conversa nova\n"
        "/cancelar — aborta a pergunta atual"
    )


# ---------------------------------------------------------------- /cancelar

async def cmd_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not liberado(update):
        return
    if WIZARD.pop(chat_id, None):
        await update.message.reply_text("Ok, esquecido.")
    else:
        await update.message.reply_text("Não havia nada em andamento.")


# ---------------------------------------------------------------- texto solto

# Cada fluxo registra aqui como responder as proprias perguntas. Fica no main
# para os modulos de comando nao precisarem se importar entre si.
_WIZARDS = {
    "chave": cmd_assistente.responder_chave,
    "credencial": cmd_credencial.responder,
}


async def texto_solto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not liberado(update):
        return

    estado = WIZARD.get(chat_id)
    if estado:
        tratar = _WIZARDS.get(estado.get("fluxo"))
        if tratar:
            await tratar(update, context)
            return

    # Sem pergunta de comando em andamento: o texto é um pedido ao Assistente
    # (10/10). Antes respondia "Não entendi".
    await cmd_assistente.conversar(update, context)


async def documento_solto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if liberado(update):
        await update.message.reply_text("Não recebo arquivos: escreva o pedido na mensagem.")


async def comando_desconhecido(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sem isto, quem ainda digita /sla ou /base ficaria sem resposta nenhuma."""
    if liberado(update):
        await update.message.reply_text(
            "Esse comando não existe mais: escreva o pedido normalmente. /start mostra os que ficaram.")


# ---------------------------------------------------------------- entrada

async def _ao_subir(app: Application) -> None:
    """Inícios agendados, do bot e do app. No --teste nada é salvo, então não roda."""
    if not cmd_assistente.TESTE:
        agendados.iniciar_vigia()


def main() -> None:
    if "--filho-do-app" in sys.argv:
        morrer_com_o_pai()

    token = credencial_servico.carregar_token()
    if not token:
        raise SystemExit(
            "Token do bot nao encontrado no Cofre do Windows.\n"
            "Configure pelo app: menu Opcoes -> Telegram."
        )

    app = Application.builder().token(token).post_init(_ao_subir).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("cancelar", cmd_cancelar))
    app.add_handler(CommandHandler("credencial", cmd_credencial.cmd_credencial))
    app.add_handler(CommandHandler("chave", cmd_assistente.cmd_chave))
    app.add_handler(CommandHandler("modelo", cmd_assistente.cmd_modelo))
    app.add_handler(CommandHandler("nova", cmd_assistente.cmd_nova))

    # Os padroes nao podem se sobrepor: o primeiro que casar e o que roda.
    app.add_handler(CallbackQueryHandler(cmd_assistente.acionar, pattern=r"^ag:\d+:\w+$"))
    app.add_handler(CallbackQueryHandler(cmd_assistente.escolher_plataforma, pattern=r"^agk:\w+$"))
    app.add_handler(CallbackQueryHandler(cmd_assistente.escolher_modelo, pattern=r"^agm:\w+$"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, texto_solto))
    app.add_handler(MessageHandler(filters.Document.ALL, documento_solto))
    app.add_handler(MessageHandler(filters.COMMAND, comando_desconhecido))

    log_bot.info("Bot no ar%s.", " (ASSISTENTE TESTE)" if cmd_assistente.TESTE else "")
    app.run_polling()


if __name__ == "__main__":
    main()
