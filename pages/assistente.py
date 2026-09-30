"""
pages/assistente.py — Tela "Assistente": chat com IA que executa os fluxos.

Só a view. Sem console de logs (decisão do usuário): o que roda aparece discreto
na conversa (título do fluxo + resumo e logs recuados), como no Claude/Gemini.
O back-end está em `state/assistente_state.py`.
"""

import reflex as rx

from state.assistente_state import AssistenteState
from components.layout import page_layout
from components.botoes import botao_primario

_SUGESTOES = [
    "Desmembre o 1234567 com os tombos 333284 e 333288, descrição \"Troca de peça\", aplicando a base do Kaspersky",
    "Coloque os chamados 1234567 e 1234568 em Aguardando Info do Fornecedor: peça solicitada",
    "Qual o SLA do chamado 1234567?",
    "O que tem na minha fila?",
]


def _botao(indice, b) -> rx.Component:
    return rx.button(
        b.rotulo,
        color_scheme=b.cor,
        variant=b.variante,
        size="1",
        radius="full",
        cursor="pointer",
        disabled=AssistenteState.rodando & (b.codigo != "cancelar"),
        on_click=AssistenteState.acionar(indice, b.codigo),
    )


_CINZA = rx.color("gray", 10)


def _icone_estado(m) -> rx.Component:
    return rx.match(
        m.estado,
        ("rodando", rx.spinner(size="1")),
        ("feito", rx.icon("check", size=14, color=rx.color("green", 10))),
        ("cancelado", rx.icon("x", size=14, color=_CINZA)),
        rx.icon("workflow", size=14, color=_CINZA),
    )


def _cartao(m, indice) -> rx.Component:
    """A ação do fluxo, no estilo discreto do Claude/Gemini: sem caixa — um
    título pequeno em cinza e, recuado com um fio à esquerda, o resumo, os
    botões e (enquanto roda) as últimas linhas de log."""
    return rx.vstack(
        rx.hstack(
            _icone_estado(m),
            rx.text(m.titulo, size="2", weight="medium", color=_CINZA),
            rx.match(
                m.estado,
                ("cancelado", rx.text("· cancelado", size="2", color=_CINZA)),
                ("feito", rx.text("· concluído", size="2", color=_CINZA)),
                rx.fragment(),
            ),
            align="center",
            spacing="2",
        ),
        rx.vstack(
            rx.cond(
                m.corpo != "",
                rx.box(rx.markdown(m.corpo), font_size="13px", color=_CINZA,
                       line_height="1.5"),
            ),
            rx.cond(
                m.aviso != "",
                rx.hstack(
                    rx.icon("triangle-alert", size=13, color=rx.color("amber", 10),
                            flex_shrink="0", margin_top="2px"),
                    rx.text(m.aviso, size="1", color=rx.color("amber", 11)),
                    spacing="2",
                    align="start",
                ),
            ),
            rx.match(
                m.estado,
                ("pendente", rx.hstack(
                    rx.foreach(m.botoes, lambda b: _botao(indice, b)),
                    spacing="2", flex_wrap="wrap", margin_top="2px",
                )),
                ("rodando", rx.vstack(
                    rx.foreach(
                        AssistenteState.logs_vivos,
                        lambda l: rx.text(l, size="1", color=rx.color("gray", 9),
                                          font_family="monospace",
                                          white_space="pre-wrap"),
                    ),
                    spacing="0",
                    margin_top="2px",
                )),
                rx.fragment(),
            ),
            spacing="2",
            align_items="stretch",
            padding_left="12px",
            margin_left="6px",
            border_left=f"2px solid {rx.color('gray', 5)}",
            width="100%",
        ),
        spacing="2",
        align_items="stretch",
        width="100%",
    )


# Coluna central da conversa, como no ChatGPT: o texto não se espalha pela
# tela inteira, mas a rolagem fica na largura toda (barra encostada na borda).
_LARGURA = "760px"


def _mensagem(m, indice) -> rx.Component:
    return rx.cond(
        m.papel == "user",
        rx.hstack(
            rx.box(
                rx.text(m.texto, white_space="pre-wrap", size="3"),
                background=rx.color("gray", 3),
                border_radius="18px",
                padding="10px 16px",
                max_width="80%",
            ),
            justify="end",
            width="100%",
        ),
        rx.vstack(
            rx.cond(
                m.texto != "",
                rx.box(
                    rx.markdown(m.texto),
                    color=rx.cond(m.erro, rx.color("red", 11), rx.color("gray", 12)),
                    font_size="15px",
                    line_height="1.6",
                    width="100%",
                ),
            ),
            rx.cond(m.titulo != "", _cartao(m, indice)),
            spacing="2",
            align_items="stretch",
            width="100%",
        ),
    )


def _sugestoes() -> rx.Component:
    """Uma abaixo da outra, em cinza claro: são só sugestões, não ações."""
    return rx.vstack(
        *[
            rx.box(
                rx.text(s, size="2", color=rx.color("gray", 10)),
                on_click=AssistenteState.set_entrada(s),
                cursor="pointer",
                padding="8px 16px",
                border_radius="10px",
                width="100%",
                opacity="0.65",
                _hover={"background": rx.color("gray", 3), "opacity": "1"},
            )
            for s in _SUGESTOES
        ],
        spacing="0",
        width="100%",
    )


def _caixa_texto() -> rx.Component:
    """Cilindro de uma linha com a seta na ponta direita. Enter envia (é um
    <input> dentro de <form>, o próprio navegador faz o submit)."""
    return rx.form(
        rx.hstack(
            rx.input(
                placeholder="Pergunte ou peça alguma coisa",
                value=AssistenteState.entrada,
                on_change=AssistenteState.set_entrada,
                disabled=AssistenteState.pensando,
                auto_complete=False,
                size="3",
                flex="1",
                min_width="0",
                # Sem a borda/fundo do Radix: quem desenha o cilindro é o box de fora.
                style={"box-shadow": "none", "background": "transparent",
                       "outline": "none", "font-size": "15px"},
            ),
            rx.icon_button(
                rx.icon("arrow-up", size=20),
                type="submit",
                radius="full",
                size="3",
                # "iris": o azul puxado para o roxo da paleta do Radix.
                color_scheme="iris",
                variant="solid",
                cursor="pointer",
                flex_shrink="0",
                disabled=AssistenteState.pensando | (AssistenteState.entrada.strip() == ""),
            ),
            align="center",
            spacing="2",
            width="100%",
            height="64px",
            padding="0 8px 0 14px",
            border=f"1px solid {rx.color('gray', 6)}",
            border_radius="9999px",
            background=rx.color("gray", 1),
            box_shadow="0 2px 12px rgba(0,0,0,0.06)",
        ),
        on_submit=AssistenteState.enviar,
        reset_on_submit=False,
        width="100%",
    )


def _pensando() -> rx.Component:
    return rx.cond(
        AssistenteState.pensando,
        rx.hstack(rx.spinner(size="2"),
                  rx.text("Pensando...", size="2", color=rx.color("gray", 11)),
                  align="center", spacing="2", width="100%"),
    )


def _inicio() -> rx.Component:
    """Conversa vazia: saudação e caixa de texto no meio da tela."""
    return rx.center(
        rx.vstack(
            rx.heading("Como posso ajudar?", size="7", weight="medium",
                       text_align="center"),
            _caixa_texto(),
            _sugestoes(),
            rx.text("Antes de alterar qualquer chamado, eu mostro um resumo para "
                    "você confirmar.", size="1", color=rx.color("gray", 10),
                    text_align="center"),
            spacing="5",
            align="center",
            width="100%",
            max_width=_LARGURA,
        ),
        width="100%",
        flex="1",
        min_height="0",
    )


def _em_conversa() -> rx.Component:
    # column-reverse: a rolagem "gruda" no fim sozinha — a mensagem nova
    # aparece sem precisar de script de auto-scroll.
    return rx.vstack(
        rx.box(
            rx.vstack(
                rx.foreach(AssistenteState.mensagens, _mensagem),
                _pensando(),
                spacing="5",
                width="100%",
                max_width=_LARGURA,
                margin_x="auto",
                padding_y="8px",
            ),
            display="flex",
            flex_direction="column-reverse",
            overflow_y="auto",
            flex="1",
            min_height="0",
            width="100%",
        ),
        rx.vstack(
            _caixa_texto(),
            rx.text("O Assistente pode errar. Confira o resumo antes de confirmar.",
                    size="1", color=rx.color("gray", 10), text_align="center"),
            spacing="2",
            align="center",
            width="100%",
            max_width=_LARGURA,
            margin_x="auto",
        ),
        spacing="3",
        width="100%",
        flex="1",
        min_height="0",
    )


def _sem_chave() -> rx.Component:
    return rx.center(
        rx.callout.root(
            rx.callout.icon(rx.icon("key-round")),
            rx.vstack(
                rx.text("Cole a chave da API da Groq (começa com gsk_). Ela fica no "
                        "Cofre de Credenciais do Windows.", size="2"),
                rx.hstack(
                    rx.input(type="password", placeholder="gsk_...",
                             value=AssistenteState.nova_chave,
                             on_change=AssistenteState.set_nova_chave, width="100%"),
                    botao_primario("Salvar", on_click=AssistenteState.salvar_chave),
                    width="100%",
                ),
                spacing="2",
                width="100%",
            ),
            width="100%",
            max_width=_LARGURA,
        ),
        width="100%",
        flex="1",
    )


def assistente_page() -> rx.Component:
    conteudo = rx.vstack(
        # Sem título (decisão do usuário): só o atalho de nova conversa, no canto.
        rx.hstack(
            rx.spacer(),
            rx.cond(
                AssistenteState.mensagens.length() > 0,
                rx.icon_button(
                    rx.icon("square-pen", size=18),
                    variant="ghost",
                    color_scheme="gray",
                    size="2",
                    cursor="pointer",
                    title="Nova conversa",
                    on_click=AssistenteState.nova_conversa,
                ),
            ),
            width="100%",
            min_height="32px",
        ),
        rx.cond(
            ~AssistenteState.chave_verificada,
            rx.fragment(),  # ainda consultando o Cofre: nao mostra nada
            rx.cond(
                AssistenteState.tem_chave,
                rx.cond(
                    AssistenteState.mensagens.length() > 0,
                    _em_conversa(),
                    _inicio(),
                ),
                _sem_chave(),
            ),
        ),
        spacing="2",
        width="100%",
        # Altura da área de conteúdo (100vh - topbar 52px - padding 32+32 do
        # layout): a conversa rola por dentro e a caixa fica sempre visível.
        height="calc(100vh - 52px - 64px)",
    )
    return page_layout(conteudo)
