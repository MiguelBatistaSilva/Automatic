"""
pages/configuracoes.py — Tela "Configurações".

Antes "Presets da Requisição" (rota /requisicao-presets); renomeada e
reorganizada em 2026-09-09 quando a whitelist do bot ("Usuários
Autorizados") migrou pra cá do pop-up "Telegram" da sidebar — as duas coisas
são config exclusiva do bot, então a página virou um agrupador com um
segmented_control de duas abas em vez de duas seções empilhadas.

Aba "Presets": cadastro dos valores fixos que o /requisicao do bot
(Telegram) oferece como BOTÃO em vez de pedir texto digitado. CRUD em
`state/requisicao_presets_state.py`, sobre `services/requisicao_presets.py`.
Campo sem nenhum valor cadastrado aqui não trava o bot: ele simplesmente
pede texto digitado pra aquele campo (ver bot/commands/cmd_requisicao.py).

Aba "Usuários Autorizados": whitelist de chat_ids que podem falar com o bot.
CRUD continua em `bot/state.py` (TelegramState) — não duplicado aqui, só a
view mudou de lugar.

A aba ativa (`RequisicaoPresetsState.aba`) é estado de UI puro, sem
persistência — mesmo padrão do `modo` em `state/desmembramento_state.py`
para o segmented_control daquela página.
"""

import reflex as rx

from state.requisicao_presets_state import RequisicaoPresetsState
from bot.state import TelegramState
from services.requisicao_campos import POR_CHAVE
from services.requisicao_presets import CAMPOS_COM_PRESET
from components.layout import page_layout
from components.botoes import botao_secundario, botao_tabela


def _valor_linha(campo: str):
    def render(valor: rx.Var, idx: rx.Var) -> rx.Component:
        return rx.hstack(
            rx.text(valor, size="2"),
            rx.spacer(),
            botao_tabela(rx.icon("x", size=13),
                        on_click=RequisicaoPresetsState.remover(campo, idx)),
            width="100%",
            align="center",
        )
    return render


def _secao_campo(campo: str) -> rx.Component:
    rotulo = POR_CHAVE[campo].rotulo
    return rx.vstack(
        rx.text(rotulo, weight="bold", size="3"),
        rx.vstack(
            rx.foreach(RequisicaoPresetsState.presets[campo], _valor_linha(campo)),
            rx.cond(
                RequisicaoPresetsState.presets[campo].length() == 0,
                rx.text(
                    "Nenhum valor cadastrado — esse campo vai pedir texto "
                    "digitado no bot.",
                    size="1", color="#6B7280",
                ),
            ),
            width="100%",
            spacing="1",
            align_items="start",
        ),
        rx.hstack(
            rx.input(
                placeholder=f"Novo valor para {rotulo}",
                value=RequisicaoPresetsState.novos_valores[campo],
                on_change=RequisicaoPresetsState.set_novo_valor(campo),
                flex="1",
            ),
            botao_secundario("+ Adicionar", on_click=RequisicaoPresetsState.adicionar(campo)),
            width="100%",
            spacing="2",
        ),
        spacing="2",
        align_items="start",
        width="100%",
        padding="12px",
        border=f"1px solid {rx.color('gray', 6)}",
        border_radius="8px",
    )


def _aba_presets() -> rx.Component:
    return rx.vstack(
        rx.text(
            "Valores fixos que aparecem como botão no /requisicao do bot do "
            "Telegram, em vez da pessoa ter que digitar. Usuário afetado e "
            "Descrição não entram aqui — são sempre texto livre, cada "
            "chamado é diferente.",
            color="#6B7280",
        ),
        *[_secao_campo(c) for c in CAMPOS_COM_PRESET],
        rx.text(RequisicaoPresetsState.status, color=RequisicaoPresetsState.status_cor),
        spacing="4",
        width="100%",
        align_items="start",
    )


def _linha_usuario_bot(item: rx.Var[tuple[str, str]]) -> rx.Component:
    chat_id, nome = item[0], item[1]
    return rx.hstack(
        rx.text(nome, size="2", weight="medium"),
        rx.text(chat_id, size="1", color="#6B7280"),
        rx.spacer(),
        botao_tabela(rx.icon("x", size=13), on_click=TelegramState.remover_usuario(chat_id)),
        width="100%",
        align="center",
        spacing="2",
    )


def _aba_usuarios_autorizados() -> rx.Component:
    return rx.vstack(
        rx.text(
            "Quem pode falar com o bot no Telegram. Depois de liberado(a) "
            "aqui, a pessoa manda /credencial pro próprio bot pra cadastrar "
            "a matrícula/senha dela.",
            color="#6B7280",
        ),
        rx.vstack(
            rx.foreach(TelegramState.usuarios, _linha_usuario_bot),
            rx.cond(
                TelegramState.usuarios.length() == 0,
                rx.text("Ninguém liberado ainda.", size="1", color="#6B7280"),
            ),
            width="100%",
            spacing="2",
        ),
        rx.hstack(
            rx.input(
                placeholder="chat_id",
                value=TelegramState.novo_chat_id,
                on_change=TelegramState.set_novo_chat_id,
                width="45%",
            ),
            rx.input(
                placeholder="Nome/apelido",
                value=TelegramState.novo_nome,
                on_change=TelegramState.set_novo_nome,
                width="55%",
            ),
            width="100%",
            spacing="2",
        ),
        botao_secundario(
            "Liberar",
            on_click=TelegramState.adicionar_usuario,
            width="100%",
        ),
        rx.text(TelegramState.status, color=TelegramState.status_cor, size="1"),
        spacing="3",
        width="100%",
        align_items="start",
        padding="12px",
        border=f"1px solid {rx.color('gray', 6)}",
        border_radius="8px",
    )


def configuracoes_page() -> rx.Component:
    conteudo = rx.vstack(
        rx.heading("Configurações", size="6"),
        rx.segmented_control.root(
            rx.segmented_control.item("Presets", value="presets"),
            rx.segmented_control.item("Usuários Autorizados", value="usuarios"),
            value=RequisicaoPresetsState.aba,
            on_change=RequisicaoPresetsState.set_aba,
        ),
        rx.match(
            RequisicaoPresetsState.aba,
            ("presets", _aba_presets()),
            ("usuarios", _aba_usuarios_autorizados()),
            _aba_presets(),
        ),
        spacing="4",
        width="100%",
        max_width="640px",
    )
    return page_layout(conteudo)
