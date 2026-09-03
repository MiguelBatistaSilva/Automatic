"""
bot/main.py — a entrada do bot do Telegram.

Este arquivo NAO tem regra de fluxo. Ele so:
  - le o token do Cofre do Windows,
  - diz quais comandos existem (registro dos handlers),
  - encaminha texto solto para o wizard certo,
  - sobe o laco da agenda.

Cada fluxo mora no seu proprio modulo:
    bot/commands/cmd_credencial.py      /credencial
    bot/commands/cmd_sla.py             /sla
    bot/commands/cmd_minhafila.py       /minhafila
    bot/commands/cmd_atendimento.py     /atendimento, /agenda
    bot/commands/cmd_informacao.py      /informacao
    bot/commands/cmd_fornecedor.py      /fornecedor
    bot/commands/cmd_usuario.py         /infousuario
    bot/commands/cmd_desmembramento.py  /base

Desde 2026-08-26 a credencial do Assyst NAO e mais unica: cada chat_id loga
com a PROPRIA matricula/senha (ver bot/services/credencial_servico.py). O /credencial
e o cadastro; os demais fluxos so leem o que ja foi cadastrado.

Rodar:
    python -m bot.main             producao — tudo vale
    python -m bot.main --teste     nada e salvo no Assyst
    python -m bot.main --simulado  o /sla tambem devolve dados falsos

`--teste` deixa Atendimento, Informacao, Fornecedor, Usuario e Requisicao
preencherem tudo e pararem antes de salvar. O /sla continua real: e leitura,
nao ha o que proteger. O /desmembrar NAO e coberto — aquele fluxo ainda nao
tem modo de teste (ver LEIA-ME.md).
"""
import asyncio
import os
import sys

# Este bloco vem ANTES dos imports do projeto de proposito: o bot/comum.py le
# estas variaveis no momento em que e importado, entao definir depois nao teria
# efeito nenhum. Flag de linha de comando em vez de variavel de ambiente porque
# a sintaxe de variavel muda conforme o terminal (PowerShell, CMD, Bash) e isso
# ja causou confusao.
if "--teste" in sys.argv:
    os.environ["BOT_ATENDIMENTO_TESTE"] = "1"
    os.environ["BOT_REQUISICAO_TESTE"] = "1"
    os.environ["BOT_INFORMACAO_TESTE"] = "1"
    os.environ["BOT_FORNECEDOR_TESTE"] = "1"
    os.environ["BOT_USUARIO_TESTE"] = "1"
if "--simulado" in sys.argv:
    os.environ["BOT_SIMULADO"] = "1"

from telegram import Update  # noqa: E402
from telegram.ext import (  # noqa: E402
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.commands import (  # noqa: E402
    cmd_atendimento,
    cmd_credencial,
    cmd_desmembramento,
    cmd_fornecedor,
    cmd_informacao,
    cmd_minhafila,
    cmd_requisicao,
    cmd_sla,
    cmd_usuario,
)
from bot.services import credencial_servico  # noqa: E402
from bot.comum import ATENDIMENTO_TESTE, SIMULADO, WIZARD, liberado, log_bot  # noqa: E402
from bot.commands.cmd_fornecedor import FORNECEDOR_TESTE  # noqa: E402
from bot.commands.cmd_informacao import INFORMACAO_TESTE  # noqa: E402
from bot.commands.cmd_requisicao import REQUISICAO_TESTE  # noqa: E402
from bot.commands.cmd_usuario import USUARIO_TESTE  # noqa: E402


# ---------------------------------------------------------------- /start

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not liberado(update):
        return

    avisos = []
    if (ATENDIMENTO_TESTE or REQUISICAO_TESTE or INFORMACAO_TESTE
            or FORNECEDOR_TESTE or USUARIO_TESTE):
        avisos.append("⚠️ MODO TESTE — nada será salvo no Assyst.")
    if SIMULADO:
        avisos.append("⚠️ O /sla está devolvendo dados falsos.")
    cabecalho = ("\n".join(avisos) + "\n\n") if avisos else ""

    await update.message.reply_text(
        f"{cabecalho}"
        "Automatic — 2N CATI\n"
        "\n"
        "CONSULTA\n"
        "/sla — SLA de um ou mais chamados\n"
        "/minhafila — lista os chamados da sua fila\n"
        "\n"
        "CONFIGURAÇÃO\n"
        "/credencial — cadastra sua matrícula/senha do Assyst (uma vez só)\n"
        "\n"
        "EXECUÇÃO\n"
        "/atendimento — agenda o início de um atendimento\n"
        "/informacao — adiciona um texto em um ou mais chamados\n"
        "/fornecedor — marca Aguardando Info do Fornecedor em um ou mais chamados\n"
        "/infousuario — marca Aguardando Info do Usuário * em um ou mais chamados\n"
        "/base — aplica uma Base de Conhecimento\n"
        "/desmembrar — cria os filhos a partir de um CSV\n"
        "/requisicao — abre uma requisição do zero, passo a passo\n"
        "\n"
        "/agenda — o que está agendado\n"
        "/cancelar — aborta a pergunta atual"
    )


# ---------------------------------------------------------------- /cancelar

async def cmd_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not liberado(update):
        return
    if WIZARD.pop(chat_id, None) or cmd_sla.esquecer(chat_id):
        await update.message.reply_text("Ok, esquecido.")
    else:
        await update.message.reply_text("Não havia nada em andamento.")


# ---------------------------------------------------------------- texto solto

# Cada fluxo registra aqui como responder as proprias perguntas. Fica no main
# para os modulos de comando nao precisarem se importar entre si.
_WIZARDS = {
    "atendimento": cmd_atendimento.responder,
    "base": cmd_desmembramento.responder,
    "credencial": cmd_credencial.responder,
    "desmembrar": cmd_desmembramento.responder_desmembrar,
    "fornecedor": cmd_fornecedor.responder,
    "informacao": cmd_informacao.responder,
    "requisicao": cmd_requisicao.responder,
    "sla": cmd_sla.responder,
    "usuario": cmd_usuario.responder,
}

# Quais fluxos aceitam arquivo, e quem trata. Fluxo que nao esta aqui ignora
# anexos — mandar planilha no meio de um /atendimento nao deve fazer nada.
# /requisicao NAO esta mais aqui: desde 2026-08-27 e passo a passo, um
# chamado por vez, sem colar arquivo (ver bot/cmd_requisicao.py).
_DOCUMENTOS = {
    "desmembrar": cmd_desmembramento.receber_documento,
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

    await update.message.reply_text(
        "Não entendi. Use /credencial, /sla, /minhafila, /atendimento, "
        "/informacao, /fornecedor, /infousuario, /base, /desmembrar, "
        "/requisicao ou /agenda."
    )


async def documento_solto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not liberado(update):
        return

    estado = WIZARD.get(chat_id)
    tratar = _DOCUMENTOS.get(estado.get("fluxo")) if estado else None
    if tratar:
        await tratar(update, context)
        return

    await update.message.reply_text(
        "Não estou esperando arquivo agora. Use /desmembrar."
    )


# ---------------------------------------------------------------- entrada

# Referencia guardada de proposito: uma task sem ninguem segurando pode ser
# coletada pelo garbage collector no meio do caminho, e o laco da agenda morreria
# sozinho, em silencio.
_LACO = None


async def _ao_subir(app) -> None:
    global _LACO
    await cmd_atendimento.avisar_indefinidos(app)

    # asyncio.create_task e nao app.create_task: o segundo avisa (PTBUserWarning)
    # que nao consegue aguardar tasks criadas antes de a aplicacao iniciar — e o
    # post_init roda justamente antes. Para um laco infinito isso nao faz falta
    # nenhuma: nao ha o que aguardar, ele so precisa morrer junto com o processo.
    _LACO = asyncio.create_task(cmd_atendimento.laco_agenda(app))


def main() -> None:
    token = credencial_servico.carregar_token()
    if not token:
        raise SystemExit(
            "Token do bot nao encontrado no Cofre do Windows.\n"
            "Configure pelo app: menu Opcoes -> Telegram."
        )

    app = Application.builder().token(token).post_init(_ao_subir).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("cancelar", cmd_cancelar))
    app.add_handler(CommandHandler("sla", cmd_sla.cmd_sla))
    app.add_handler(CommandHandler("minhafila", cmd_minhafila.cmd_minhafila))
    app.add_handler(CommandHandler("atendimento", cmd_atendimento.cmd_atendimento))
    app.add_handler(CommandHandler("agenda", cmd_atendimento.cmd_agenda))
    app.add_handler(CommandHandler("informacao", cmd_informacao.cmd_informacao))
    app.add_handler(CommandHandler("fornecedor", cmd_fornecedor.cmd_fornecedor))
    app.add_handler(CommandHandler("infousuario", cmd_usuario.cmd_usuario))
    app.add_handler(CommandHandler("credencial", cmd_credencial.cmd_credencial))
    app.add_handler(CommandHandler("base", cmd_desmembramento.cmd_base))
    app.add_handler(CommandHandler("desmembrar", cmd_desmembramento.cmd_desmembrar))
    app.add_handler(CommandHandler("requisicao", cmd_requisicao.cmd_requisicao))

    # Os padroes nao podem se sobrepor: o primeiro que casar e o que roda.
    app.add_handler(CallbackQueryHandler(cmd_sla.escolher_fila, pattern=r"^fila:\d+$"))
    app.add_handler(CallbackQueryHandler(cmd_atendimento.confirmar, pattern=r"^at:(ok|nao)$"))
    app.add_handler(CallbackQueryHandler(cmd_atendimento.cancelar_item, pattern=r"^at:del:"))
    app.add_handler(CallbackQueryHandler(cmd_desmembramento.escolher_kb, pattern=r"^bc:kb:\d+$"))
    app.add_handler(CallbackQueryHandler(cmd_desmembramento.decidir_checkpoint, pattern=r"^bc:cp:"))
    app.add_handler(CallbackQueryHandler(cmd_desmembramento.confirmar, pattern=r"^bc:(ok|nao)$"))
    app.add_handler(CallbackQueryHandler(cmd_desmembramento.escolher_modo, pattern=r"^ds:modo:"))
    app.add_handler(CallbackQueryHandler(cmd_desmembramento.escolher_kb_desmembrar, pattern=r"^ds:kb:\d+$"))
    app.add_handler(CallbackQueryHandler(cmd_desmembramento.decidir_checkpoint_desmembrar, pattern=r"^ds:cp:"))
    app.add_handler(CallbackQueryHandler(cmd_desmembramento.confirmar_desmembrar, pattern=r"^ds:(ok|nao)$"))

    app.add_handler(CallbackQueryHandler(cmd_requisicao.escolher_valor, pattern=r"^rq:v:\d+$"))
    app.add_handler(CallbackQueryHandler(cmd_requisicao.pular, pattern=r"^rq:pular$"))
    app.add_handler(CallbackQueryHandler(cmd_requisicao.confirmar, pattern=r"^rq:(ok|nao)$"))
    app.add_handler(CallbackQueryHandler(cmd_informacao.confirmar, pattern=r"^in:(ok|nao)$"))
    app.add_handler(CallbackQueryHandler(cmd_fornecedor.confirmar, pattern=r"^fn:(ok|nao)$"))
    app.add_handler(CallbackQueryHandler(cmd_usuario.confirmar, pattern=r"^us:(ok|nao)$"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, texto_solto))
    app.add_handler(MessageHandler(filters.Document.ALL, documento_solto))

    modos = []
    if SIMULADO:
        modos.append("SLA SIMULADO")
    if ATENDIMENTO_TESTE:
        modos.append("ATENDIMENTO TESTE")
    if INFORMACAO_TESTE:
        modos.append("INFORMACAO TESTE")
    if FORNECEDOR_TESTE:
        modos.append("FORNECEDOR TESTE")
    if USUARIO_TESTE:
        modos.append("USUARIO TESTE")
    log_bot.info("Bot no ar%s.", f" ({', '.join(modos)})" if modos else "")
    app.run_polling()


if __name__ == "__main__":
    main()
