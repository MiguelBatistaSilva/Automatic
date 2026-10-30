"""
pages/configuracoes.py — Tela "Configurações".

Antes "Presets da Requisição" (rota /requisicao-presets); renomeada e
reorganizada em 2026-09-09 quando a whitelist do bot ("Usuários
Autorizados") migrou pra cá do pop-up "Telegram" da sidebar. Em 2026-09-15
ganhou a terceira aba: a página "Bases de Conhecimento" (rota /kb) deixou de
existir como rota própria e virou a aba "Bases de Conhecimento" aqui — as
três são telas de cadastro sem fluxo/navegador, então faz sentido virarem
abas de um agrupador em vez de itens separados na sidebar.

Aba "Referência" (substituiu a "Presets" em 28/10): consulta e edição das
tabelas do banco de referência (itens da Requisição, técnicos, filas,
edifícios), em `state/referencia_state.py` sobre `services/dados/referencia.py`.
Edição só na máquina com .git (a de quem publica); nas outras, só consulta.

Aba "Usuários Autorizados": whitelist de chat_ids que podem falar com o bot.
CRUD continua em `bot/state.py` (TelegramState) — não duplicado aqui, só a
view mudou de lugar.

Aba "Bases de Conhecimento": cadastro de keyword+artigo usado pelos modos
Criar + Base e Só Base do Desmembramento (tela e bot, ambos lêem
o banco SQLite via `services/dados/kb_store.py`). CRUD continua em
`state/kb_state.py` (KBState) — não duplicado aqui, só a view mudou de
lugar, igual às outras duas abas.

A aba ativa (`ReferenciaState.aba`) é estado de UI puro, sem
persistência — mesmo padrão do `modo` em `state/desmembramento_state.py`
para o segmented_control daquela página.
"""

import reflex as rx

from state.referencia_state import ReferenciaState, TABELAS
from state.kb_state import KBState
from bot.state import TelegramState
from components.layout import page_layout
from components.botoes import botao_primario, botao_secundario, botao_tabela


def _celula(valor: rx.Var) -> rx.Component:
    return rx.table.cell(valor)


def _linha_referencia(linha: rx.Var, idx: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.foreach(linha, _celula),
        rx.cond(
            ReferenciaState.editavel,
            rx.table.cell(botao_tabela(rx.icon("x", size=13),
                                       on_click=ReferenciaState.remover(idx))),
        ),
    )


def _campo_novo(coluna: rx.Var, i: rx.Var) -> rx.Component:
    return rx.input(placeholder=coluna, value=ReferenciaState.novo[i],
                    on_change=lambda v: ReferenciaState.set_novo(i, v), flex="1")


def _aba_referencia() -> rx.Component:
    return rx.vstack(
        rx.text(
            "O que o Assistente e o /requisicao do bot usam para completar e "
            "conferir a Requisição: itens, técnicos, filas e edifícios. Fica "
            "em services/agente/conhecimento/referencia/ e vai a todos pela "
            "atualização.",
            color="#6B7280",
        ),
        rx.cond(
            ReferenciaState.editavel,
            rx.callout("Depois de editar, commite: é o update que leva a "
                       "mudança às outras máquinas.", icon="info", size="1"),
            rx.callout("Só consulta: a edição é feita na máquina de publicação "
                       "(a deste computador seria sobrescrita no próximo update).",
                       icon="lock", size="1", color_scheme="gray"),
        ),
        rx.foreach(
            ReferenciaState.alertas,
            lambda a: rx.callout(a + " Corrija em services/agente/conhecimento/"
                                 "requisicao/tipos_solicitacao.md ou cadastre o valor aqui.",
                                 icon="triangle_alert", size="1", color_scheme="orange"),
        ),
        rx.hstack(
            rx.select(list(TABELAS), value=ReferenciaState.tabela,
                      on_change=ReferenciaState.set_tabela),
            rx.input(placeholder="Buscar...", value=ReferenciaState.busca,
                     on_change=ReferenciaState.set_busca, flex="1"),
            rx.text(ReferenciaState.visiveis.length().to_string() + " de "
                    + ReferenciaState.total.to_string(), size="1", color="#6B7280"),
            width="100%",
            align="center",
            spacing="2",
        ),
        rx.cond(
            ReferenciaState.editavel,
            rx.hstack(
                rx.foreach(ReferenciaState.colunas, _campo_novo),
                botao_secundario("+ Adicionar", on_click=ReferenciaState.adicionar),
                width="100%",
                spacing="2",
            ),
        ),
        rx.text(ReferenciaState.status, color=ReferenciaState.status_cor, size="1"),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.foreach(ReferenciaState.colunas,
                               lambda c: rx.table.column_header_cell(c)),
                    rx.cond(ReferenciaState.editavel, rx.table.column_header_cell("")),
                ),
            ),
            rx.table.body(rx.foreach(ReferenciaState.visiveis, _linha_referencia)),
            width="100%",
            variant="surface",
            size="1",
        ),
        spacing="3",
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
        ),
        spacing="3",
        width="100%",
        align_items="start",
    )


def _linha_kb(item: rx.Var, idx: rx.Var) -> rx.Component:
    return rx.table.row(
        rx.table.cell(item.nome_artigo),
        rx.table.cell(rx.code(item.keyword)),
        rx.table.cell(
            botao_tabela("Remover", on_click=KBState.remover(idx)),
        ),
    )


def _dialog_nova_base() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Adicionar Base de Conhecimento"),
            rx.dialog.description(
                "Palavra-chave usada na busca da Base de Conhecimento do "
                "Assyst, e o título exato do artigo que ela deve encontrar.",
                color="#6B7280",
                size="2",
            ),
            rx.vstack(
                rx.text("Palavra-chave", weight="bold", size="2"),
                rx.input(placeholder="ex: kaspersky", value=KBState.novo_keyword,
                         on_change=KBState.set_novo_keyword, width="100%"),
                rx.text("Título do artigo", weight="bold", size="2", margin_top="0.5em"),
                rx.input(placeholder="ex: BC - Instalação do Kaspersky",
                         value=KBState.novo_artigo, on_change=KBState.set_novo_artigo,
                         width="100%"),
                spacing="1",
                align_items="start",
                width="100%",
                margin_top="1em",
            ),
            rx.text(KBState.status, color=KBState.status_cor, size="2",
                    margin_top="0.75em"),
            rx.hstack(
                rx.spacer(),
                rx.dialog.close(botao_secundario("Cancelar")),
                botao_primario("Adicionar", on_click=KBState.adicionar,
                               color_scheme="green"),
                spacing="3",
                width="100%",
                margin_top="1.25em",
                align="center",
            ),
            max_width="420px",
        ),
        open=KBState.aberto,
        on_open_change=KBState.set_aberto,
    )


def _aba_base_conhecimento() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.text(
                "Bases usadas pelos modos Criar + Base e Só Base do "
                "Desmembramento — na tela e no /base e /desmembrar do bot.",
                color="#6B7280",
            ),
            rx.spacer(),
            botao_primario("+ Adicionar Base", on_click=KBState.abrir,
                           color_scheme="green"),
            width="100%",
            align="center",
        ),
        rx.cond(
            KBState.entries,
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Título do Artigo"),
                        rx.table.column_header_cell("Palavra-chave"),
                        rx.table.column_header_cell(""),
                    ),
                ),
                rx.table.body(rx.foreach(KBState.entries, _linha_kb)),
                width="100%",
                variant="surface",
            ),
            rx.text("Nenhuma base cadastrada ainda.", size="1", color="#6B7280"),
        ),
        _dialog_nova_base(),
        spacing="4",
        width="100%",
        align_items="start",
    )


def configuracoes_page() -> rx.Component:
    conteudo = rx.vstack(
        rx.heading("Configurações", size="6"),
        rx.segmented_control.root(
            rx.segmented_control.item("Bases de Conhecimento", value="kb"),
            rx.segmented_control.item("Referência", value="referencia"),
            rx.segmented_control.item("Usuários Autorizados", value="usuarios"),
            value=ReferenciaState.aba,
            on_change=ReferenciaState.set_aba,
        ),
        rx.match(
            ReferenciaState.aba,
            ("kb", _aba_base_conhecimento()),
            ("referencia", _aba_referencia()),
            ("usuarios", _aba_usuarios_autorizados()),
            _aba_base_conhecimento(),
        ),
        spacing="4",
        width="100%",
        # As abas de tabela (Bases de Conhecimento e Referência) ocupam a
        # página toda; a de Usuários Autorizados é formulário estreito.
        max_width=rx.cond(ReferenciaState.aba == "usuarios", "640px", "100%"),
    )
    return page_layout(conteudo)
