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

Aba "Modelos de Despacho" (09/11): os testes e o defeito que o Assistente põe
no script de despacho ao Serviço de Operações, por defeito. Grava em
services/agente/conhecimento/chamados/despachos.md (`state/despachos_state.py`);
mesma regra da Referência: edita só onde há .git.

A aba ativa (`ReferenciaState.aba`) é estado de UI puro, sem
persistência — mesmo padrão do `modo` em `state/desmembramento_state.py`
para o segmented_control daquela página.
"""

import reflex as rx

from state.referencia_state import ReferenciaState, TABELAS
from state.kb_state import KBState
from state.despachos_state import DespachosState
from bot.state import TelegramState
from components.layout import page_layout
from components.botoes import (botao_perigo, botao_primario, botao_secundario,
                               botao_tabela)


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
            "O que o Assistente usa para completar e "
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


# --------------------------------------------------------------------------- #
# Modelos de Despacho
# --------------------------------------------------------------------------- #

def _item_despacho(m: rx.Var) -> rx.Component:
    ativo = DespachosState.sel.to_string() == m["i"]
    return rx.box(
        rx.text(m["nome"], size="2", weight="medium"),
        rx.hstack(
            rx.badge(m["tipo"], size="1", variant="soft"),
            rx.text(m["n"], size="1", color="#6B7280"),
            spacing="2",
            align="center",
        ),
        on_click=DespachosState.abrir(m["i"]),
        padding="8px 10px",
        border_radius="6px",
        cursor="pointer",
        width="100%",
        background=rx.cond(ativo, rx.color("accent", 3), "transparent"),
        border=rx.cond(ativo, f"1px solid {rx.color('accent', 7)}",
                       f"1px solid {rx.color('gray', 4)}"),
        _hover={"background": rx.color("accent", 2)},
    )


def _rotulo(texto: str) -> rx.Component:
    return rx.text(texto, weight="bold", size="2")


def _dica(texto: str) -> rx.Component:
    return rx.text(texto, size="1", color="#6B7280")


def _previa_despacho() -> rx.Component:
    # Mesmas cores do Assyst: rótulo azul-marinho em negrito, resposta vermelha.
    azul, vermelho = "#1E3A8A", "#DC2626"
    return rx.box(
        rx.text("Testes realizado:", weight="bold", color=azul, size="2"),
        rx.foreach(DespachosState.prev_testes,
                   lambda t: rx.text(t, color=vermelho, size="2")),
        rx.text("Defeito apresentado:", weight="bold", color=azul, size="2",
                margin_top="0.75em"),
        rx.text(DespachosState.prev_defeito, color=vermelho, size="2"),
        padding="12px",
        border=f"1px solid {rx.color('gray', 5)}",
        border_radius="8px",
        background="white",
        width="100%",
    )


def _form_despacho() -> rx.Component:
    so_leitura = ~DespachosState.editavel
    return rx.vstack(
        rx.hstack(
            rx.vstack(
                _rotulo("Nome"),
                rx.input(value=DespachosState.f_nome, on_change=DespachosState.set_f_nome,
                         placeholder="Mouse — scroll", read_only=so_leitura, width="100%"),
                spacing="1", flex="2",
            ),
            rx.vstack(
                _rotulo("Tipo"),
                rx.select(DespachosState.tipos, value=DespachosState.f_tipo,
                          on_change=DespachosState.set_f_tipo, placeholder="Tipo",
                          disabled=so_leitura, width="100%"),
                spacing="1", flex="1",
            ),
            width="100%",
            spacing="3",
        ),
        _rotulo("Pedidos"),
        _dica("Palavras que o técnico usa para esse defeito, separadas por "
              "vírgula. É por elas que o Assistente escolhe o modelo."),
        rx.input(value=DespachosState.f_pedidos, on_change=DespachosState.set_f_pedidos,
                 placeholder="scroll, rolagem, rodinha", read_only=so_leitura, width="100%"),
        rx.foreach(DespachosState.avisos,
                   lambda a: rx.callout(a, icon="triangle_alert", size="1",
                                        color_scheme="orange", width="100%")),
        _rotulo("Testes realizados"),
        _dica("Um por linha, sem ';' no fim (o script põe). Ex.: \"Realizado "
              "teste em outra porta USB, sem sucesso\"."),
        rx.text_area(value=DespachosState.f_testes, on_change=DespachosState.set_f_testes,
                     read_only=so_leitura, rows="9", width="100%"),
        _rotulo("Defeito apresentado"),
        rx.input(value=DespachosState.f_defeito, on_change=DespachosState.set_f_defeito,
                 placeholder="Falha no sensor de rolagem (scroll)", read_only=so_leitura,
                 width="100%"),
        _rotulo("Prévia no script"),
        _previa_despacho(),
        rx.cond(
            DespachosState.editavel,
            rx.hstack(
                botao_primario("Salvar", on_click=DespachosState.salvar,
                               color_scheme="green", disabled=~DespachosState.alterado),
                botao_secundario("Descartar", on_click=DespachosState.descartar,
                                 disabled=~DespachosState.alterado),
                rx.spacer(),
                rx.cond(
                    ~DespachosState.novo,
                    botao_perigo(
                        rx.cond(DespachosState.confirmar_exclusao,
                                "Confirmar exclusão", "Excluir"),
                        on_click=DespachosState.excluir),
                ),
                width="100%",
                spacing="2",
                margin_top="0.5em",
            ),
        ),
        spacing="2",
        width="100%",
        align_items="start",
    )


def _aba_despachos() -> rx.Component:
    return rx.vstack(
        rx.text(
            "Testes e defeito que o Assistente põe no script de despacho ao "
            "Serviço de Operações, por defeito. A IA só escolhe o modelo; o "
            "texto sai exatamente como escrito aqui. Fica em "
            "services/agente/conhecimento/chamados/despachos.md.",
            color="#6B7280",
        ),
        rx.cond(
            DespachosState.editavel,
            rx.callout("Salvar já vale para o Assistente desta máquina; commite "
                       "para levar às outras.", icon="info", size="1"),
            rx.callout("Só consulta: a edição é feita na máquina de publicação "
                       "(a deste computador seria sobrescrita no próximo update).",
                       icon="lock", size="1", color_scheme="gray"),
        ),
        rx.text(DespachosState.status, color=DespachosState.status_cor, size="2"),
        rx.flex(
            rx.vstack(
                rx.select(DespachosState.filtros, value=DespachosState.filtro,
                          on_change=DespachosState.set_filtro, width="100%"),
                rx.input(placeholder="Buscar...", value=DespachosState.busca,
                         on_change=DespachosState.set_busca, width="100%"),
                rx.hstack(
                    _dica(DespachosState.lista.length().to_string() + " de "
                          + DespachosState.total.to_string()),
                    rx.spacer(),
                    rx.cond(DespachosState.editavel,
                            botao_secundario("+ Novo modelo",
                                             on_click=DespachosState.criar)),
                    width="100%",
                    align="center",
                ),
                rx.vstack(
                    rx.foreach(DespachosState.lista, _item_despacho),
                    spacing="1",
                    width="100%",
                    max_height="65vh",
                    overflow_y="auto",
                    padding_right="4px",
                ),
                spacing="2",
                width=rx.breakpoints(initial="100%", md="320px"),
                flex_shrink="0",
            ),
            rx.box(
                rx.cond(
                    (DespachosState.sel >= 0) | DespachosState.novo,
                    _form_despacho(),
                    _dica("Escolha um modelo na lista."),
                ),
                flex="1",
                width="100%",
                padding="12px",
                border=f"1px solid {rx.color('gray', 6)}",
                border_radius="8px",
            ),
            direction=rx.breakpoints(initial="column", md="row"),
            spacing="4",
            width="100%",
            align="start",
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
                "Desmembramento — na tela e no Assistente.",
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
            rx.segmented_control.item("Modelos de Despacho", value="despachos"),
            rx.segmented_control.item("Usuários Autorizados", value="usuarios"),
            value=ReferenciaState.aba,
            on_change=ReferenciaState.set_aba,
        ),
        rx.match(
            ReferenciaState.aba,
            ("kb", _aba_base_conhecimento()),
            ("referencia", _aba_referencia()),
            ("despachos", _aba_despachos()),
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
