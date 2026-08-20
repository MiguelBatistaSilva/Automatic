"""
bot/cmd_sla.py — /sla: analise de SLA.

Unico fluxo do bot que so LE: abre o chamado, le o historico de acoes e calcula.
Nao altera nada, entao nao precisa de confirmacao antes de rodar.
"""
import asyncio
import re
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bot import credencial_servico
from bot.comum import MAX_CHAMADOS, SIMULADO, WIZARD, liberado, log_bot, quem
from services.sla_engine import FILAS
from bot.sla_service import analisar_chamados

_FILAS = list(FILAS.keys())

# Chamados aguardando a escolha da fila, por chat. Em memoria de proposito:
# reiniciar o bot descarta pedidos pela metade, que e o que se quer.
_PENDENTES: dict[int, list[str]] = {}


def _formatar(resultados, fila) -> str:
    linhas = [f"Fila: {fila}", ""]
    for r in resultados:
        if not r["ok"]:
            linhas.append(f"⚠️ {r['numero']} — {r['erro']}")
            linhas.append("")
            continue

        marca = "🔴" if r["estourado"] else "🟢"
        linhas.append(f"{marca} {r['numero']} — {r['usuario']}")
        linhas.append(f"      Início: {r['inicio']}  ({r['acoes']} ações)")
        if r["estourado"]:
            linhas.append(f"      {r['mensagem']}  ·  gasto {r['tempo_gasto']}")
        else:
            linhas.append(f"      Gasto {r['tempo_gasto']}  ·  restam {r['tempo_restante']}")
        linhas.append("")

    estourados = sum(1 for r in resultados if r["ok"] and r["estourado"])
    falhas = sum(1 for r in resultados if not r["ok"])
    resumo = [f"{len(resultados)} chamado(s)"]
    if estourados:
        resumo.append(f"{estourados} estourado(s)")
    if falhas:
        resumo.append(f"{falhas} sem resultado")
    linhas.append(" · ".join(resumo))

    return "\n".join(linhas)


def _simular(chamados, fila):
    """Resultado falso, para testar o bot sem tocar no Assyst.

    Inclui de proposito um chamado estourado e um que falhou: o caminho feliz e
    o que menos precisa de teste.
    """
    time.sleep(2)  # finge o tempo do navegador

    resultados = []
    for i, numero in enumerate(chamados):
        if i == 2:
            resultados.append({
                "numero": numero, "ok": False,
                "erro": "Nao consegui abrir o chamado ou ler o historico",
            })
            continue
        estourado = (i == 1)
        resultados.append({
            "numero": numero,
            "ok": True,
            "usuario": "FULANO DE TAL (SIMULADO)",
            "fila": fila,
            "inicio": "12/08/2026 09:14",
            "tempo_gasto": "05h 20min" if estourado else "01h 10min",
            "tempo_restante": "00h 00min" if estourado else "01h 50min",
            "estourado": estourado,
            "mensagem": "ESTOURADO há 02h 20min" if estourado else "RESTAM 01h 50min",
            "acoes": 7,
        })
    return resultados


# Aceita separado por espaco, virgula, ponto-e-virgula ou quebra de linha — no
# celular o usuario cola de qualquer jeito.
def _parse(texto: str) -> list[str]:
    return [c for c in re.split(r"[\s,;]+", texto) if c]


async def cmd_sla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not liberado(update):
        return

    # Atalho: /sla 123456 123457 pula direto pra escolha da fila, sem perguntar.
    if context.args:
        await _pedir_fila(update, chat_id, _parse(" ".join(context.args)))
        return

    WIZARD[chat_id] = {"fluxo": "sla", "passo": "chamados"}
    await update.message.reply_text(
        "Quais chamados? Manda um ou mais números, separados por espaço, "
        "vírgula ou cada um numa linha.\n\n(/cancelar para desistir)"
    )


async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if WIZARD.get(chat_id, {}).get("passo") != "chamados":
        return

    if await _pedir_fila(update, chat_id, _parse(update.message.text)):
        WIZARD.pop(chat_id, None)


async def _pedir_fila(update: Update, chat_id: int, chamados: list[str]) -> bool:
    """Valida os chamados e mostra o teclado de filas. True se seguiu adiante
    (usado pelo `responder` para saber se pode fechar o wizard ou deixar a
    pessoa tentar de novo)."""
    if not chamados:
        await update.message.reply_text("Não entendi. Ex.: 123456 123457")
        return False
    if len(chamados) > MAX_CHAMADOS:
        await update.message.reply_text(
            f"São {len(chamados)} chamados; o limite é {MAX_CHAMADOS} por vez."
        )
        return False

    _PENDENTES[chat_id] = chamados
    teclado = InlineKeyboardMarkup(
        [[InlineKeyboardButton(nome, callback_data=f"fila:{i}")]
         for i, nome in enumerate(_FILAS)]
    )
    await update.message.reply_text(
        f"{len(chamados)} chamado(s). Qual a fila?", reply_markup=teclado
    )
    return True


async def escolher_fila(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = query.message.chat_id
    await query.answer()  # tira o "reloginho" do botao no celular

    if not liberado(update):
        return

    chamados = _PENDENTES.pop(chat_id, None)
    if not chamados:
        # Acontece se o bot reiniciou entre o /sla e o toque no botao.
        await query.edit_message_text("Esse pedido expirou. Mande /sla de novo.")
        return

    fila = _FILAS[int(query.data.split(":")[1])]
    matricula, senha = credencial_servico.carregar()

    if not SIMULADO and not senha:
        await query.edit_message_text(
            "A credencial do bot ainda não foi configurada nesta máquina "
            "(menu Opções -> Telegram, no app)."
        )
        return

    await query.edit_message_text(
        f"🔎 Analisando {len(chamados)} chamado(s) na fila {fila}..."
    )
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    autor = quem(update)

    def log(msg, tipo="info"):
        log_bot.info("[%s] %s", autor, msg)

    try:
        # asyncio.to_thread porque o Playwright dos fluxos e SINCRONO e se prende
        # a thread que o criou — rodar direto aqui travaria o bot inteiro.
        if SIMULADO:
            resultados = await asyncio.to_thread(_simular, chamados, fila)
        else:
            resultados = await asyncio.to_thread(
                analisar_chamados, chamados, fila, matricula, senha, log
            )
    except Exception as e:
        log_bot.exception("Falha na analise para %s", matricula)
        await context.bot.send_message(chat_id, f"A automação quebrou no meio: {e}")
        return

    await context.bot.send_message(chat_id, _formatar(resultados, fila))


def esquecer(chat_id) -> bool:
    """Descarta um /sla pela metade. Usado pelo /cancelar."""
    return _PENDENTES.pop(chat_id, None) is not None
