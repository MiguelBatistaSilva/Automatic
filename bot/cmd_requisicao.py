"""
bot/cmd_requisicao.py — /requisicao: abre chamados do zero.

Uma requisicao por linha, campos separados por `;`. A ordem dos campos e
mostrada na hora, derivada do catalogo (services/requisicao_campos.py), entao
ela nunca fica desatualizada em relacao ao fluxo.

Duas diferencas em relacao aos outros comandos:

- a entrada e VALIDADA antes de qualquer coisa, e o erro cita a linha. Nao faz
  sentido abrir o navegador para descobrir na linha 7 que faltava um campo.
- nao existe checkpoint aqui. Se quebrar no meio, nao ha retomada — por isso o
  relatorio final lista linha a linha o que foi criado, para quem for repetir
  colar so o que faltou.
"""
import asyncio
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot import credencial_servico, requisicao_service
from bot.comum import MAX_CHAMADOS, WIZARD, liberado, log_bot, quem

# Preenche tudo e PARA antes de salvar. O app deliberadamente nao expoe isso ao
# operador; aqui e variavel de ambiente, para teste, nao botao.
REQUISICAO_TESTE = os.getenv("BOT_REQUISICAO_TESTE") == "1"


def _formatar(resultados, modo_teste) -> str:
    linhas = []
    for r in resultados:
        if r["ok"]:
            numero = r["numero"] or "(modo teste, sem número)"
            linhas.append(f"🟢 linha {r['linha']} — {numero} · {r['usuario']}")
        else:
            linhas.append(f"❌ linha {r['linha']} — {r['erro']} · {r['usuario']}")

    criadas = sum(1 for r in resultados if r["ok"])
    linhas.append("")
    linhas.append(f"{criadas} de {len(resultados)} criada(s)")

    if criadas < len(resultados):
        # Sem checkpoint, retomar e responsabilidade de quem cola.
        linhas.append(
            "Não há retomada automática: para repetir, cole apenas as linhas que falharam."
        )
    if modo_teste:
        linhas.append("\n⚠️ MODO TESTE: nada foi salvo no Assyst.")
    return "\n".join(linhas)


async def cmd_requisicao(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not liberado(update):
        return

    WIZARD[chat_id] = {"fluxo": "requisicao", "passo": "linhas"}
    aviso = "\n\n⚠️ MODO TESTE ligado: nada será salvo." if REQUISICAO_TESTE else ""
    await update.message.reply_text(
        "Cole as requisições, uma por linha, nesta ordem:\n\n"
        f"{requisicao_service.ordem_dos_campos()}\n\n"
        "Ou envie um arquivo .txt/.csv com as linhas."
        f"{aviso}\n\n(/cancelar para desistir)"
    )


async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _receber(update, WIZARD[update.effective_chat.id], update.message.text)


async def receber_documento(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    estado = WIZARD.get(chat_id)
    arquivo = await update.message.document.get_file()
    bruto = await arquivo.download_as_bytearray()
    # utf-8-sig: o Excel grava com BOM, que colaria no primeiro campo.
    await _receber(update, estado, bytes(bruto).decode("utf-8-sig", errors="replace"))


async def _receber(update, estado, texto) -> None:
    if not estado or estado.get("passo") != "linhas":
        return

    requisicoes, erro = requisicao_service.validar(texto)
    if erro:
        # O erro do parse ja cita o numero da linha — repassar literal e melhor
        # do que reescrever com palavras minhas.
        await update.message.reply_text(f"❌ {erro}\n\nCorrija e cole de novo.")
        return
    if len(requisicoes) > MAX_CHAMADOS:
        await update.message.reply_text(
            f"São {len(requisicoes)} linhas; o limite é {MAX_CHAMADOS} por vez."
        )
        return

    estado["requisicoes"] = requisicoes
    estado["passo"] = "confirmar"

    amostra = "\n".join(
        f"  {i}. {r.get('usuario_afetado', '?')} — {r.get('resumo', '')[:40]}"
        for i, r in enumerate(requisicoes[:5], 1)
    )
    if len(requisicoes) > 5:
        amostra += f"\n  ... e mais {len(requisicoes) - 5}"

    cabecalho = (
        "MODO TESTE — nada será salvo.\n\n" if REQUISICAO_TESTE
        else f"⚠️ Isto ABRE {len(requisicoes)} chamado(s) no Assyst.\n\n"
    )
    await update.message.reply_text(
        f"{cabecalho}{amostra}\n\nConfirma?",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Confirmar", callback_data="rq:ok"),
            InlineKeyboardButton("✖️ Cancelar", callback_data="rq:nao"),
        ]]),
    )


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

    matricula, senha = credencial_servico.carregar()
    if not senha:
        await query.edit_message_text(
            "A credencial do bot ainda não foi configurada nesta máquina "
            "(menu Opções -> Telegram, no app)."
        )
        return

    requisicoes = estado["requisicoes"]
    await query.edit_message_text(f"▶️ Abrindo {len(requisicoes)} requisição(ões)...")

    autor = quem(update)

    def log(msg, tipo="info"):
        log_bot.info("[%s] %s", autor, msg)

    try:
        resultados = await asyncio.to_thread(
            requisicao_service.criar_lote,
            requisicoes, matricula, senha, log, REQUISICAO_TESTE,
        )
    except Exception as e:
        log_bot.exception("Falha na requisicao de %s", matricula)
        await context.bot.send_message(chat_id, f"❌ A automação quebrou: {e}")
        return

    await context.bot.send_message(chat_id, _formatar(resultados, REQUISICAO_TESTE))
