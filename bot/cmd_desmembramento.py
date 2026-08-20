"""
bot/cmd_desmembramento.py — /base: aplica uma Base de Conhecimento.

Por ora so o modo "So Base" do Desmembramento: aplica a BC em chamados filhos
que JA EXISTEM. E o unico dos tres modos que nao cria chamado — por isso foi o
primeiro a ser exposto.

Os modos Completo e So Criar entram aqui depois. Eles CRIAM chamado no Assyst e
hoje nao tem modo de teste, entao so devem ser expostos quando houver um jeito
de exercita-los sem sujar o sistema.

O dialogo de checkpoint (Retomar / Do zero / Cancelar) e a parte que mais se
parece com a tela: mesma decisao, mesmos tres caminhos, so que em botao.
"""
import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot import credencial_servico, desmembramento_service
from bot.comum import MAX_CHAMADOS, WIZARD, liberado, log_bot, quem


def _teclado_kbs(kbs) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(nome, callback_data=f"bc:kb:{i}")]
         for i, nome in enumerate(kbs)]
    )


def _resumo(estado, iniciar_do_zero=False) -> str:
    filhos = estado["filhos"]
    amostra = ", ".join(filhos[:5]) + (" ..." if len(filhos) > 5 else "")
    modo = "recomeçando do zero" if iniciar_do_zero else "continuando de onde parou"
    return (
        f"Confirma?\n\n"
        f"Aplicar a base {estado['kb']}\n"
        f"em {len(filhos)} chamado(s): {amostra}\n\n"
        f"({modo})"
    )


def _formatar(r) -> str:
    if not r.get("ok"):
        return f"❌ {r.get('erro', 'falhou')}"

    marcas = {"concluido": "🟢", "salvo": "🟡", "pendente": "⚪"}
    linhas = [f"Base: {r['kb']}", ""]
    for d in r["detalhe"]:
        linhas.append(f"{marcas.get(d['status'], '⚠️')} {d['chamado']} — {d['status']}")
    linhas.append("")
    linhas.append(f"{r['concluidos']} de {r['total']} concluído(s)")
    if r["concluidos"] < r["total"]:
        linhas.append("Mande /base com a mesma lista para retomar de onde parou.")
    return "\n".join(linhas)


# ---------------------------------------------------------------- wizard

async def cmd_base(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not liberado(update):
        return

    kbs = desmembramento_service.kbs_disponiveis()
    if not kbs:
        await update.message.reply_text(
            "Não há Base de Conhecimento cadastrada nesta máquina. "
            "Cadastre pelo app antes."
        )
        return

    WIZARD[chat_id] = {"fluxo": "base", "passo": "filhos", "kbs": kbs,
                       "quem": quem(update)}
    await update.message.reply_text(
        "Cole os chamados filhos, um por linha.\n(/cancelar para desistir)"
    )


async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    estado = WIZARD[chat_id]

    if estado["passo"] != "filhos":
        return

    filhos = [l.strip() for l in update.message.text.splitlines() if l.strip()]
    if not filhos:
        await update.message.reply_text("Não achei nenhum número. Cole um por linha.")
        return
    if len(filhos) > MAX_CHAMADOS:
        await update.message.reply_text(
            f"São {len(filhos)} chamados; o limite é {MAX_CHAMADOS} por vez."
        )
        return

    estado["filhos"] = filhos
    estado["passo"] = "kb"
    await update.message.reply_text(
        f"{len(filhos)} chamado(s). Qual a Base de Conhecimento?",
        reply_markup=_teclado_kbs(estado["kbs"]),
    )


async def escolher_kb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = query.message.chat_id
    await query.answer()
    if not liberado(update):
        return

    estado = WIZARD.get(chat_id)
    if not estado or estado.get("passo") != "kb":
        await query.edit_message_text("Esse pedido expirou. Mande /base de novo.")
        return

    estado["kb"] = estado["kbs"][int(query.data.split(":")[2])]
    chave = desmembramento_service.chave_bc(estado["filhos"])
    estado["chave"] = chave
    sit = desmembramento_service.situacao(chave)

    if sit["estado"] == desmembramento_service.CORROMPIDO:
        # Tratar arquivo ilegivel como "novo" faria o fluxo reprocessar tudo
        # achando que e a primeira vez. Melhor parar e mandar resolver no app.
        WIZARD.pop(chat_id, None)
        await query.edit_message_text(
            f"O checkpoint desta lista ({chave}) está ilegível. Não vou "
            "continuar às cegas — resolva pelo app antes."
        )
        return

    if sit["estado"] == desmembramento_service.CONCLUIDO:
        estado["passo"] = "checkpoint"
        await query.edit_message_text(
            f"Essa lista já foi concluída.\n\n{sit['resumo']}\n\nO que faço?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refazer do zero", callback_data="bc:cp:zero")],
                [InlineKeyboardButton("✖️ Cancelar", callback_data="bc:cp:nao")],
            ]),
        )
        return

    if sit["estado"] == desmembramento_service.PENDENTE:
        estado["passo"] = "checkpoint"
        await query.edit_message_text(
            f"Essa lista ficou pela metade.\n\n{sit['resumo']}\n\nO que faço?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("▶️ Retomar de onde parou", callback_data="bc:cp:retomar")],
                [InlineKeyboardButton("🔄 Começar do zero", callback_data="bc:cp:zero")],
                [InlineKeyboardButton("✖️ Cancelar", callback_data="bc:cp:nao")],
            ]),
        )
        return

    estado["passo"] = "confirmar"
    await query.edit_message_text(
        _resumo(estado),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Confirmar", callback_data="bc:ok"),
            InlineKeyboardButton("✖️ Cancelar", callback_data="bc:nao"),
        ]]),
    )


async def decidir_checkpoint(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = query.message.chat_id
    await query.answer()
    if not liberado(update):
        return

    estado = WIZARD.get(chat_id)
    if not estado or estado.get("passo") != "checkpoint":
        await query.edit_message_text("Esse pedido expirou. Mande /base de novo.")
        return

    acao = query.data.split(":")[2]
    if acao == "nao":
        WIZARD.pop(chat_id, None)
        await query.edit_message_text("Cancelado. Nada foi executado.")
        return

    estado["do_zero"] = (acao == "zero")
    await query.edit_message_text(_resumo(estado, estado["do_zero"]))
    await _rodar(context, chat_id, estado)


async def confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = query.message.chat_id
    await query.answer()
    if not liberado(update):
        return

    estado = WIZARD.get(chat_id)
    if not estado or estado.get("passo") != "confirmar":
        await query.edit_message_text("Esse pedido expirou. Mande /base de novo.")
        return

    if query.data == "bc:nao":
        WIZARD.pop(chat_id, None)
        await query.edit_message_text("Cancelado. Nada foi executado.")
        return

    estado["do_zero"] = False
    await query.edit_message_text(_resumo(estado))
    await _rodar(context, chat_id, estado)


# ================================================================ /desmembrar
#
# Modos Completo e So Criar. Diferente do /base, estes CRIAM CHAMADO no Assyst e
# nao tem modo de teste — cada linha do CSV vira um chamado de verdade. Por isso
# o resumo antes de confirmar e enfatico, e o CSV e mostrado contado por linhas.

def _resumo_desmembrar(estado, iniciar_do_zero=False) -> str:
    total = len(estado["linhas"])
    kb = estado.get("kb")
    modo = "recomeçando do zero" if iniciar_do_zero else "continuando de onde parou"
    return (
        f"⚠️ Isto CRIA {total} chamado(s) no Assyst.\n\n"
        f"Referência: {estado['pai']}\n"
        f"Linhas no CSV: {total}\n"
        f"Base de Conhecimento: {kb if kb else 'não aplicar (só criar)'}\n"
        f"Descrição: {estado['descricao'][:60]}"
        f"{'...' if len(estado['descricao']) > 60 else ''}\n\n"
        f"({modo})\n\nConfirma?"
    )


def _formatar_desmembrar(r) -> str:
    if not r.get("ok"):
        return f"❌ {r.get('erro', 'falhou')}"

    marcas = {"concluido": "🟢", "salvo": "🟡", "pendente": "⚪"}
    linhas = [f"Referência: {r['chave']}"]
    if r["kb"]:
        linhas.append(f"Base: {r['kb']}")
    linhas.append("")
    for d in r["detalhe"]:
        filho = d["filho"] or "sem número"
        linhas.append(f"{marcas.get(d['status'], '⚠️')} linha {d['linha']} — {filho}")
    linhas.append("")
    linhas.append(f"{r['criados']} de {r['total']} criado(s) · {r['concluidos']} concluído(s)")
    if r["concluidos"] < r["total"]:
        linhas.append("Mande /desmembrar com a mesma referência para retomar.")
    return "\n".join(linhas)


async def cmd_desmembrar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not liberado(update):
        return

    WIZARD[chat_id] = {"fluxo": "desmembrar", "passo": "modo",
                       "quem": quem(update)}
    await update.message.reply_text(
        "Desmembramento — qual modo?\n(/cancelar para desistir)",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Criar + Base", callback_data="ds:modo:completo")],
            [InlineKeyboardButton("Só Criar", callback_data="ds:modo:criar")],
        ]),
    )


async def escolher_modo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = query.message.chat_id
    await query.answer()
    if not liberado(update):
        return

    estado = WIZARD.get(chat_id)
    if not estado or estado.get("passo") != "modo":
        await query.edit_message_text("Esse pedido expirou. Mande /desmembrar de novo.")
        return

    estado["modo"] = query.data.split(":")[2]
    estado["passo"] = "pai"
    rotulo = "Criar + Base" if estado["modo"] == "completo" else "Só Criar"
    await query.edit_message_text(
        f"Modo: {rotulo}.\n\nQual o chamado de referência (o pai)?"
    )


async def responder_desmembrar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    estado = WIZARD[chat_id]
    passo = estado["passo"]

    if passo == "pai":
        estado["pai"] = update.message.text.strip()
        estado["passo"] = "csv"
        await update.message.reply_text(
            f"Referência {estado['pai']}.\n\n"
            "Agora o CSV: cole o conteúdo (com a linha de cabeçalho) "
            "ou envie o arquivo .csv aqui."
        )
        return

    if passo == "csv":
        await _receber_csv(update, estado, update.message.text)
        return

    if passo == "descricao":
        estado["descricao"] = update.message.text.strip()
        await _apos_descricao(update.message, chat_id, estado)
        return


async def receber_documento(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Aceita o CSV como arquivo — no celular e bem melhor que colar texto."""
    chat_id = update.effective_chat.id
    if not liberado(update):
        return

    estado = WIZARD.get(chat_id)
    if not estado or estado.get("passo") != "csv":
        await update.message.reply_text(
            "Não estou esperando arquivo agora. Use /desmembrar."
        )
        return

    arquivo = await update.message.document.get_file()
    bruto = await arquivo.download_as_bytearray()
    # utf-8-sig: o Excel grava CSV com BOM, que apareceria colado no nome da
    # primeira coluna e estragaria o cabecalho em silencio.
    texto = bytes(bruto).decode("utf-8-sig", errors="replace")
    await _receber_csv(update, estado, texto)


async def _receber_csv(update, estado, texto) -> None:
    colunas, linhas = desmembramento_service.parse_csv(texto)
    if not linhas:
        await update.message.reply_text(
            "Não achei linhas de dados. O CSV precisa de cabeçalho + ao menos uma linha."
        )
        return
    if len(linhas) > MAX_CHAMADOS:
        await update.message.reply_text(
            f"São {len(linhas)} linhas; o limite é {MAX_CHAMADOS} por vez."
        )
        return

    estado["csv"] = texto
    estado["linhas"] = linhas
    estado["passo"] = "descricao"
    await update.message.reply_text(
        f"{len(linhas)} linha(s), colunas: {', '.join(colunas)}\n\n"
        "Qual a descrição dos chamados?"
    )


async def _apos_descricao(mensagem, chat_id, estado) -> None:
    """Com a descricao definida: pede a KB (modo completo) ou vai para o resumo."""
    if estado["modo"] == "completo":
        kbs = desmembramento_service.kbs_disponiveis()
        if not kbs:
            WIZARD.pop(chat_id, None)
            await mensagem.reply_text(
                "Não há Base de Conhecimento cadastrada nesta máquina."
            )
            return
        estado["kbs"] = kbs
        estado["passo"] = "kb"
        await mensagem.reply_text(
            "Qual a Base de Conhecimento?",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(n, callback_data=f"ds:kb:{i}")]
                 for i, n in enumerate(kbs)]
            ),
        )
        return

    estado["kb"] = None
    await _checar_checkpoint(mensagem, chat_id, estado)


async def escolher_kb_desmembrar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = query.message.chat_id
    await query.answer()
    if not liberado(update):
        return

    estado = WIZARD.get(chat_id)
    if not estado or estado.get("passo") != "kb":
        await query.edit_message_text("Esse pedido expirou. Mande /desmembrar de novo.")
        return

    estado["kb"] = estado["kbs"][int(query.data.split(":")[2])]
    await query.edit_message_text(f"Base: {estado['kb']}")
    await _checar_checkpoint(query.message, chat_id, estado)


async def _checar_checkpoint(mensagem, chat_id, estado) -> None:
    """Mesma decisao do dialogo da tela: retomar, do zero, ou cancelar."""
    chave = estado["pai"]
    estado["chave"] = chave
    sit = desmembramento_service.situacao(chave)

    if sit["estado"] == desmembramento_service.CORROMPIDO:
        WIZARD.pop(chat_id, None)
        await mensagem.reply_text(
            f"O checkpoint da referência {chave} está ilegível. Não vou continuar "
            "às cegas — recomeçar recriaria chamados que já existem."
        )
        return

    if sit["estado"] in (desmembramento_service.PENDENTE, desmembramento_service.CONCLUIDO):
        estado["passo"] = "checkpoint"
        concluido = sit["estado"] == desmembramento_service.CONCLUIDO
        botoes = []
        if not concluido:
            botoes.append([InlineKeyboardButton(
                "▶️ Retomar de onde parou", callback_data="ds:cp:retomar")])
        botoes.append([InlineKeyboardButton(
            "🔄 Criar tudo de novo", callback_data="ds:cp:zero")])
        botoes.append([InlineKeyboardButton("✖️ Cancelar", callback_data="ds:cp:nao")])
        await mensagem.reply_text(
            f"Essa referência {'já foi concluída' if concluido else 'ficou pela metade'}.\n\n"
            f"{sit['resumo']}\n\n"
            "⚠️ 'Criar tudo de novo' CRIA chamados duplicados dos que já existem.\n\n"
            "O que faço?",
            reply_markup=InlineKeyboardMarkup(botoes),
        )
        return

    estado["passo"] = "confirmar"
    await mensagem.reply_text(
        _resumo_desmembrar(estado),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Confirmar", callback_data="ds:ok"),
            InlineKeyboardButton("✖️ Cancelar", callback_data="ds:nao"),
        ]]),
    )


async def decidir_checkpoint_desmembrar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = query.message.chat_id
    await query.answer()
    if not liberado(update):
        return

    estado = WIZARD.get(chat_id)
    if not estado or estado.get("passo") != "checkpoint":
        await query.edit_message_text("Esse pedido expirou. Mande /desmembrar de novo.")
        return

    acao = query.data.split(":")[2]
    if acao == "nao":
        WIZARD.pop(chat_id, None)
        await query.edit_message_text("Cancelado. Nada foi criado.")
        return

    estado["do_zero"] = (acao == "zero")
    await query.edit_message_text(_resumo_desmembrar(estado, estado["do_zero"]))
    await _rodar_desmembrar(context, chat_id, estado)


async def confirmar_desmembrar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = query.message.chat_id
    await query.answer()
    if not liberado(update):
        return

    estado = WIZARD.get(chat_id)
    if not estado or estado.get("passo") != "confirmar":
        await query.edit_message_text("Esse pedido expirou. Mande /desmembrar de novo.")
        return

    if query.data == "ds:nao":
        WIZARD.pop(chat_id, None)
        await query.edit_message_text("Cancelado. Nada foi criado.")
        return

    estado["do_zero"] = False
    await query.edit_message_text("Confirmado.")
    await _rodar_desmembrar(context, chat_id, estado)


async def _rodar_desmembrar(context, chat_id, estado) -> None:
    WIZARD.pop(chat_id, None)

    matricula, senha = credencial_servico.carregar()
    if not senha:
        await context.bot.send_message(
            chat_id,
            "A credencial do bot ainda não foi configurada nesta máquina "
            "(menu Opções -> Telegram, no app).",
        )
        return

    pai, total = estado["pai"], len(estado["linhas"])
    aviso = await context.bot.send_message(
        chat_id, f"▶️ Criando {total} chamado(s) a partir de {pai}..."
    )

    autor = estado.get("quem", matricula)

    def log(msg, tipo="info"):
        log_bot.info("[%s] %s", autor, msg)

    async def acompanhar():
        visto = -1
        while True:
            await asyncio.sleep(10)
            feitos, tot = desmembramento_service.progresso(pai, total)
            if feitos != visto:
                visto = feitos
                try:
                    await aviso.edit_text(f"▶️ Criando: {feitos}/{tot} concluído(s)...")
                except Exception:
                    pass

    tarefa = asyncio.create_task(acompanhar())
    try:
        resultado = await asyncio.to_thread(
            desmembramento_service.criar_filhos,
            pai, estado["csv"], estado["descricao"], matricula, senha,
            estado.get("kb"), log, estado.get("do_zero", False),
        )
    except Exception as e:
        log_bot.exception("Falha no desmembramento de %s", matricula)
        await context.bot.send_message(chat_id, f"❌ A automação quebrou: {e}")
        return
    finally:
        tarefa.cancel()

    await context.bot.send_message(chat_id, _formatar_desmembrar(resultado))

    # O TXT com os numeros dos filhos: na tela ele abre no Bloco de Notas da
    # maquina do operador — aqui isso abriria numa tela que ninguem ve, entao vai
    # como arquivo no chat.
    txt = desmembramento_service.caminho_filhos(pai)
    if txt.exists() and txt.stat().st_size > 0:
        try:
            with open(txt, "rb") as f:
                await context.bot.send_document(chat_id, f, filename=txt.name)
        except Exception:
            log_bot.exception("Nao consegui enviar o TXT de filhos")


async def _rodar(context, chat_id, estado) -> None:
    """Executa o modo So Base, mostrando o andamento e relatando no fim."""
    WIZARD.pop(chat_id, None)

    matricula, senha = credencial_servico.carregar()
    if not senha:
        await context.bot.send_message(
            chat_id,
            "A credencial do bot ainda não foi configurada nesta máquina "
            "(menu Opções -> Telegram, no app).",
        )
        return

    filhos, kb, chave = estado["filhos"], estado["kb"], estado["chave"]
    total = len(filhos)

    aviso = await context.bot.send_message(
        chat_id, f"▶️ Aplicando a base em {total} chamado(s)..."
    )

    autor = estado.get("quem", matricula)

    def log(msg, tipo="info"):
        log_bot.info("[%s] %s", autor, msg)

    # O FluxoBCPW nao devolve nada enquanto roda, mas grava cada linha no
    # checkpoint. Entao o andamento vem de LER o checkpoint de fora, sem
    # depender de o worker conseguir falar com o laco async.
    async def acompanhar():
        visto = -1
        while True:
            await asyncio.sleep(10)
            feitos, tot = desmembramento_service.progresso(chave, total)
            if feitos != visto:
                visto = feitos
                try:
                    await aviso.edit_text(
                        f"▶️ Aplicando a base: {feitos}/{tot} concluído(s)..."
                    )
                except Exception:
                    pass  # edicao repetida ou rate limit; nao e motivo para parar

    tarefa = asyncio.create_task(acompanhar())
    try:
        resultado = await asyncio.to_thread(
            desmembramento_service.aplicar_base,
            filhos, kb, matricula, senha, log, estado.get("do_zero", False),
        )
    except Exception as e:
        log_bot.exception("Falha no modo So Base de %s", matricula)
        await context.bot.send_message(chat_id, f"❌ A automação quebrou: {e}")
        return
    finally:
        tarefa.cancel()

    await context.bot.send_message(chat_id, _formatar(resultado))
