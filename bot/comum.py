"""
bot/comum.py — o que todos os comandos do bot usam.

Existe para os modulos de comando (cmd_*.py) nao precisarem se importar entre si
so para compartilhar a autorizacao, o logger e o estado das conversas. Aqui nao
mora regra de fluxo nenhuma — so o que e comum a todos.
"""
import logging
import os

from telegram import Update

from bot import usuarios

# --------------------------------------------------------------------- flags

# SLA com dados falsos, sem abrir o Chrome nem tocar no Assyst.
SIMULADO = os.getenv("BOT_SIMULADO") == "1"

# Atendimento em modo teste: o fluxo vai ate preencher a descricao e PARA antes
# de clicar em "Salvar acao". Exercita o caminho inteiro sem alterar o chamado.
ATENDIMENTO_TESTE = os.getenv("BOT_ATENDIMENTO_TESTE") == "1"

MAX_CHAMADOS = 15   # o Assyst leva alguns segundos por chamado; acima disso o
                    # usuario fica sem resposta tempo demais e acha que travou

# --------------------------------------------------------------------- log

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)

# A httpx (usada por baixo pela python-telegram-bot) registra cada requisicao em
# nivel INFO com a URL inteira — e o token do bot vai DENTRO da URL. Num log em
# arquivo, numa maquina compartilhada, isso e a senha do bot em texto puro.
# Silenciada aqui; os logs do proprio bot continuam em INFO.
logging.getLogger("httpx").setLevel(logging.WARNING)

log_bot = logging.getLogger("bot")

# --------------------------------------------------------------------- estado

# Perguntas em andamento, por chat. Em memoria de proposito: uma conversa pela
# metade nao deve sobreviver a um restart. Cada entrada tem ao menos "fluxo"
# (qual comando esta perguntando) e "passo" (em que pergunta esta).
#
# Nao confundir com a AGENDA (bot/agenda.py), que vai para disco: aquilo e
# compromisso assumido, isto e conversa inacabada.
WIZARD: dict[int, dict] = {}


# --------------------------------------------------------------- autorizacao

def liberado(update: Update) -> bool:
    """A whitelist. Unica barreira entre o bot e qualquer pessoa do Telegram."""
    chat_id = update.effective_chat.id
    if usuarios.autorizado(chat_id):
        return True

    # Quem nao esta na whitelist nao recebe resposta nenhuma — nem para
    # descobrir que o bot existe. Mas o terminal registra quem tentou: e assim
    # que se cadastra um colega novo. A pessoa manda qualquer mensagem, voce le
    # a linha abaixo e libera pelo pop-up Telegram (menu de opcoes do app).
    u = update.effective_user
    nome = " ".join(filter(None, [u.first_name, u.last_name])) if u else "?"
    arroba = f"@{u.username}" if u and u.username else "sem @"
    log_bot.warning(
        "NAO AUTORIZADO: %s (%s) | chat_id=%s | para liberar: menu Opcoes "
        "-> Telegram, no app.",
        nome, arroba, chat_id,
    )
    return False


def quem(update: Update) -> str:
    """Nome de quem falou, para o log e para os avisos."""
    u = update.effective_user
    return (u.first_name or str(u.id)) if u else "?"
