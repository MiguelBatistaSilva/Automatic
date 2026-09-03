"""
bot/cmd_atendimento.py — /atendimento e /agenda: Iniciar Atendimento agendado.

O que o bot faz aqui que a tela nao faz: o relogio corre na maquina do bot, nao
na do usuario. A pessoa agenda pelo celular e vai embora; o aviso chega quando
executa. Pela tela, ela precisaria deixar o app de pe ate a hora marcada.

O laco de fundo (`laco_agenda`) e o coracao disso — ele acorda de tempos em
tempos, executa o que venceu e avisa quem pediu.
"""
import asyncio
import time
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot import agenda
from bot.comum import ATENDIMENTO_TESTE, WIZARD, liberado, log_bot, quem
from bot.services import credencial_servico, atendimento_service

INTERVALO_AGENDA_S = 20    # de quanto em quanto tempo o laco checa os vencidos
TOLERANCIA_ATRASO_S = 120  # depois disso o agendamento vira PERDIDO, nao roda


# ---------------------------------------------------------------- wizard

def _parse_quando(texto: str):
    """Interpreta a data/hora digitada. Devolve datetime ou None.

    Aceita as tres formas que a pessoa naturalmente digita no celular:
        25/08/2026 14:30
        25/08 14:30        (ano corrente)
        14:30              (hoje)
    """
    t = texto.strip().replace("h", ":").replace("-", "/")
    agora = datetime.now()
    tentativas = [
        ("%d/%m/%Y %H:%M", {}),
        ("%d/%m/%y %H:%M", {}),
        ("%d/%m %H:%M", {"year": agora.year}),
        ("%H:%M", {"year": agora.year, "month": agora.month, "day": agora.day}),
    ]
    for formato, preencher in tentativas:
        try:
            dt = datetime.strptime(t, formato)
        except ValueError:
            continue
        return dt.replace(second=0, microsecond=0, **preencher)
    return None


async def cmd_atendimento(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not liberado(update):
        return
    WIZARD[chat_id] = {"fluxo": "atendimento", "passo": "chamado"}
    await update.message.reply_text(
        "Qual o número do chamado?\n(/cancelar para desistir)"
    )


async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Trata a resposta de uma pergunta do /atendimento."""
    chat_id = update.effective_chat.id
    estado = WIZARD[chat_id]
    texto = update.message.text.strip()

    if estado["passo"] == "chamado":
        estado["chamado"] = texto
        estado["passo"] = "quando"
        await update.message.reply_text(
            f"Chamado {texto}.\n\nPara quando?\n"
            "Ex.: 25/08 14:30  ·  25/08/2026 14:30  ·  14:30 (hoje)"
        )
        return

    if estado["passo"] == "quando":
        quando = _parse_quando(texto)
        if quando is None:
            await update.message.reply_text("Não entendi a data. Tente: 25/08 14:30")
            return
        if quando.timestamp() <= time.time():
            await update.message.reply_text(
                f"{quando.strftime('%d/%m/%Y %H:%M')} já passou. "
                "Informe um horário futuro."
            )
            return

        estado["quando"] = quando
        estado["passo"] = "confirmar"

        faltam = quando.timestamp() - time.time()
        horas, minutos = int(faltam // 3600), int((faltam % 3600) // 60)
        aviso = "\n\n⚠️ MODO TESTE: não vai salvar a ação." if ATENDIMENTO_TESTE else ""

        teclado = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Confirmar", callback_data="at:ok"),
            InlineKeyboardButton("✖️ Cancelar", callback_data="at:nao"),
        ]])
        await update.message.reply_text(
            f"Confirma?\n\n"
            f"Chamado {estado['chamado']}\n"
            f"Iniciar em {quando.strftime('%d/%m/%Y às %H:%M')}"
            f"  (daqui a {horas}h{minutos:02d}){aviso}",
            reply_markup=teclado,
        )


async def confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = query.message.chat_id
    await query.answer()
    if not liberado(update):
        return

    estado = WIZARD.pop(chat_id, None)
    if not estado or estado.get("passo") != "confirmar":
        await query.edit_message_text("Esse pedido expirou. Mande /atendimento de novo.")
        return

    if query.data == "at:nao":
        await query.edit_message_text("Cancelado. Nada foi agendado.")
        return

    quando = estado["quando"]
    item = agenda.adicionar(
        chat_id=chat_id,
        quem=quem(update),
        chamado=estado["chamado"],
        quando_ts=quando.timestamp(),
        quando_label=quando.strftime("%d/%m/%Y %H:%M"),
    )
    log_bot.info("[%s] agendou %s para %s", item.quem, item.chamado, item.quando_label)
    await query.edit_message_text(
        f"⏰ Agendado: chamado {item.chamado} em {item.quando_label}.\n"
        "Te aviso aqui quando executar."
    )


# ---------------------------------------------------------------- /agenda

async def cmd_agenda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not liberado(update):
        return

    itens = agenda.listar(chat_id=chat_id, apenas_abertos=True)
    if not itens:
        await update.message.reply_text("Você não tem nada agendado.")
        return

    for item in itens:
        marca = "⏳" if item.status == agenda.PENDENTE else "▶️"
        teclado = None
        if item.status == agenda.PENDENTE:
            teclado = InlineKeyboardMarkup([[
                InlineKeyboardButton("🗑 Cancelar", callback_data=f"at:del:{item.id}")
            ]])
        await update.message.reply_text(
            f"{marca} Chamado {item.chamado} — {item.quando_label}",
            reply_markup=teclado,
        )


async def cancelar_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = query.message.chat_id
    await query.answer()
    if not liberado(update):
        return

    item = agenda.cancelar(query.data.split(":")[2], chat_id)
    if item:
        await query.edit_message_text(
            f"🗑 Cancelado: chamado {item.chamado} ({item.quando_label})."
        )
    else:
        # Ja executou, ja foi cancelado, ou e de outra pessoa.
        await query.edit_message_text("Não consegui cancelar — talvez já tenha executado.")


# ---------------------------------------------------------------- laco de fundo

async def _executar_vencidos(app, itens) -> None:
    """Roda os agendamentos que venceram e avisa quem pediu.

    Agrupa por pessoa e cada uma loga com a PRÓPRIA credencial (ver
    `credencial_servico.py`) — por isso a sessão de navegador também é uma
    por pessoa, não mais uma sessão só compartilhada. Se uma pessoa não tem
    credencial cadastrada, só os agendamentos DELA falham; os das outras
    seguem normalmente.
    """
    por_pessoa: dict[int, list] = {}
    for item in itens:
        por_pessoa.setdefault(item.chat_id, []).append(item)

    for chat_id, grupo in por_pessoa.items():
        matricula, senha = credencial_servico.carregar_de(chat_id)
        if not senha:
            for item in grupo:
                agenda.concluir(item.id, False, "Credencial pessoal nao configurada")
            await app.bot.send_message(
                chat_id,
                "⚠️ Chegou a hora dos seus agendamentos, mas você ainda não "
                "cadastrou sua credencial. Mande /credencial e agende de novo.",
            )
            continue

        chamados = [i.chamado for i in grupo]

        # O nome de quem agendou, nao a matricula: o log e sobre QUEM pediu, e
        # todas as linhas do bot seguem esse mesmo formato.
        def log(msg, tipo="info", _q=grupo[0].quem):
            log_bot.info("[%s] %s", _q, msg)

        try:
            resultados = await asyncio.to_thread(
                atendimento_service.iniciar_lote,
                chamados, matricula, senha, log, ATENDIMENTO_TESTE,
            )
        except Exception as e:
            log_bot.exception("Falha no lote de atendimento de %s", matricula)
            for item in grupo:
                agenda.concluir(item.id, False, str(e))
            await app.bot.send_message(chat_id, f"❌ A automação quebrou: {e}")
            continue

        linhas = []
        for item in grupo:
            ok, detalhe = resultados.get(item.chamado, (False, "sem resultado"))
            agenda.concluir(item.id, ok, detalhe)
            if ok:
                linhas.append(f"✅ {item.chamado} — atendimento iniciado")
            else:
                linhas.append(f"❌ {item.chamado} — {detalhe or 'falhou'}")
        if ATENDIMENTO_TESTE:
            linhas.append("\n⚠️ MODO TESTE: a ação não foi salva no chamado.")
        await app.bot.send_message(chat_id, "\n".join(linhas))


async def laco_agenda(app) -> None:
    """Acorda de tempos em tempos, executa o que venceu e avisa os perdidos.

    Enquanto nada vence, isto NAO toca no Assyst: so le o arquivo da agenda e
    volta a dormir. O navegador so abre quando ha agendamento vencido.
    """
    pendentes = len(agenda.listar(apenas_abertos=True))
    log_bot.info(
        "Agendamentos: %d pendente(s). Verificando a cada %ss.",
        pendentes, INTERVALO_AGENDA_S,
    )
    while True:
        try:
            rodar, perdidos = agenda.separar_vencidos(time.time(), TOLERANCIA_ATRASO_S)

            for item in perdidos:
                await app.bot.send_message(
                    item.chat_id,
                    f"⚠️ Agendamento perdido: chamado {item.chamado}, marcado para "
                    f"{item.quando_label}. O bot não estava no ar na hora e o "
                    f"atendimento precisa iniciar no horário certo, então não executei.",
                )

            if rodar:
                await _executar_vencidos(app, rodar)

        except Exception:
            # O laco NAO pode morrer: se ele cair, todos os agendamentos futuros
            # deixam de acontecer em silencio.
            log_bot.exception("Erro no laco da agenda")

        await asyncio.sleep(INTERVALO_AGENDA_S)


async def avisar_indefinidos(app) -> None:
    """Na subida, avisa sobre execucoes que ficaram sem desfecho conhecido."""
    for item in agenda.carregar_ao_subir():
        try:
            await app.bot.send_message(
                item.chat_id,
                f"⚠️ O bot caiu enquanto executava o chamado {item.chamado} "
                f"({item.quando_label}). Não sei dizer se a ação chegou a ser "
                f"salva — confira no Assyst.",
            )
        except Exception:
            log_bot.exception("Nao consegui avisar sobre o item %s", item.id)
