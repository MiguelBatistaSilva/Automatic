"""
bot/cmd_minhafila.py — /minhafila: consulta da fila do tecnico.

Segundo fluxo do bot que so LE (o primeiro e o /sla): abre a fila do tecnico
logado e lista Referencia, Usuario afetado e Secao de cada chamado. Nao altera
nada, entao nao precisa de confirmacao antes de rodar — e um comando direto,
sem wizard.
"""
import asyncio

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bot.comum import liberado, log_bot, quem
from bot.services import credencial_servico
from bot.services.minhafila_service import consultar_fila

# Telegram recusa mensagem acima de 4096 caracteres; fica bem abaixo disso para
# nao arriscar contar errado (emoji, acentos) perto do limite.
_TAMANHO_MAX_MSG = 3500


def _formatar_linha(item: dict) -> str:
    return f"{item['referencia']} — {item['afetado'] or '--'} — {item['secao'] or '--'}"


def _montar_mensagens(chamados: list[dict]) -> list[str]:
    """Quebra a fila em varias mensagens quando ela e grande demais para uma so."""
    if not chamados:
        return ["Fila vazia — nenhum chamado atribuído a você no momento."]

    linhas = [f"Minha Fila — {len(chamados)} chamado(s)", ""]
    linhas.extend(_formatar_linha(c) for c in chamados)

    mensagens = []
    atual: list[str] = []
    tamanho = 0
    for linha in linhas:
        if atual and tamanho + len(linha) + 1 > _TAMANHO_MAX_MSG:
            mensagens.append("\n".join(atual))
            atual, tamanho = [], 0
        atual.append(linha)
        tamanho += len(linha) + 1
    if atual:
        mensagens.append("\n".join(atual))
    return mensagens


async def cmd_minhafila(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not liberado(update):
        return

    matricula, senha = credencial_servico.carregar_de(chat_id)
    if not senha:
        await update.message.reply_text(
            "Você ainda não cadastrou sua credencial do Assyst. Mande "
            "/credencial primeiro."
        )
        return

    await update.message.reply_text("🔎 Consultando sua fila...")
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    autor = quem(update)

    def log(msg, tipo="info"):
        log_bot.info("[%s] %s", autor, msg)

    try:
        # asyncio.to_thread porque o Playwright dos fluxos e SINCRONO e se
        # prende a thread que o criou — rodar direto aqui travaria o bot inteiro.
        chamados = await asyncio.to_thread(consultar_fila, matricula, senha, log)
    except Exception as e:
        log_bot.exception("Falha ao consultar a fila para %s", matricula)
        await context.bot.send_message(chat_id, f"A automação quebrou no meio: {e}")
        return

    if chamados is None:
        await context.bot.send_message(
            chat_id,
            "Não consegui abrir sua fila — confira sua credencial e tente de novo.",
        )
        return

    for msg in _montar_mensagens(chamados):
        await context.bot.send_message(chat_id, msg)
