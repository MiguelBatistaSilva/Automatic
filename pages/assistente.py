"""
pages/assistente.py — Tela "Assistente": chat com IA que executa os fluxos.

Só a view. Sem console de logs (decisão do usuário): o que roda aparece discreto
na conversa (título do fluxo + resumo e logs recuados), como no Claude/Gemini.
O back-end está em `state/assistente_state.py`.
"""

import reflex as rx

from state.assistente_state import AssistenteState
from state.api_keys_state import ROTA as ROTA_API_KEYS
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


def _icone_passo(estado) -> rx.Component:
    return rx.match(
        estado,
        ("rodando", rx.spinner(size="1")),
        ("ok", rx.icon("check", size=13, color=rx.color("green", 10))),
        ("erro", rx.icon("x", size=13, color=rx.color("red", 10))),
        ("pulado", rx.icon("minus", size=13, color=_CINZA)),
        rx.icon("circle", size=11, color=_CINZA),
    )


def _logs_vivos() -> rx.Component:
    return rx.vstack(
        rx.foreach(
            AssistenteState.logs_vivos,
            lambda l: rx.text(l, size="1", color=rx.color("gray", 9),
                              font_family="monospace", white_space="pre-wrap"),
        ),
        spacing="0",
    )


def _passo(m, p) -> rx.Component:
    """Um passo do plano. Num plano de um passo só, o título já é o do
    cartão — aqui aparece só o resumo (e os logs enquanto roda)."""
    return rx.vstack(
        rx.cond(
            m.multi,
            rx.hstack(
                _icone_passo(p.estado),
                rx.text(p.titulo, size="2", weight="medium", color=rx.color("gray", 11)),
                rx.cond(p.estado == "pulado",
                        rx.text("· não executado", size="1", color=_CINZA)),
                align="center",
                spacing="2",
            ),
        ),
        rx.cond(
            p.corpo != "",
            rx.box(rx.markdown(p.corpo), font_size="13px", color=_CINZA,
                   line_height="1.5", overflow_x="auto",
                   padding_left=rx.cond(m.multi, "21px", "0")),
        ),
        # Lista da Requisição: colada de volta no chat, vira o MESMO lote (06/10).
        rx.cond(
            p.copiar != "",
            rx.box(
                rx.button(
                    rx.icon("copy", size=13), "Copiar lista",
                    variant="soft", color_scheme="gray", size="1", radius="full",
                    cursor="pointer",
                    on_click=[rx.set_clipboard(p.copiar),
                              rx.toast("Lista copiada. Cole no chat para refazer este mesmo lote.")],
                ),
                padding_left=rx.cond(m.multi, "21px", "0"),
            ),
        ),
        rx.cond(
            p.estado == "rodando",
            rx.box(_logs_vivos(), padding_left=rx.cond(m.multi, "21px", "0")),
        ),
        spacing="1",
        align_items="stretch",
        width="100%",
    )


def _seta(m) -> rx.Component:
    return rx.cond(m.aberto,
                   rx.icon("chevron-down", size=14, color=_CINZA),
                   rx.icon("chevron-right", size=14, color=_CINZA))


def _atividade(m) -> rx.Component:
    """O que o agente fez antes de responder (consultas, passos montados)."""
    return rx.vstack(
        rx.foreach(
            m.atividade,
            lambda a: rx.hstack(
                rx.icon("dot", size=14, color=_CINZA, flex_shrink="0"),
                rx.text(a, size="1", color=_CINZA),
                spacing="1", align="start",
            ),
        ),
        spacing="1",
        width="100%",
    )


def _logs_guardados(m) -> rx.Component:
    """Log completo da execução, para conferir depois (rola por dentro)."""
    return rx.box(
        rx.foreach(
            m.logs,
            lambda l: rx.text(l, size="1", color=rx.color("gray", 9),
                              font_family="monospace", white_space="pre-wrap"),
        ),
        max_height="260px",
        overflow_y="auto",
        width="100%",
        padding="6px 8px",
        border_radius="6px",
        background=rx.color("gray", 2),
    )


def _corpo_recuado(*filhos) -> rx.Component:
    return rx.vstack(
        *filhos,
        spacing="2",
        align_items="stretch",
        padding_left="12px",
        margin_left="6px",
        border_left=f"2px solid {rx.color('gray', 5)}",
        width="100%",
    )


def _expansor_atividade(m, indice) -> rx.Component:
    """Resposta comum (sem cartão) que teve consultas: uma linha recolhida
    ("1 consulta") que abre a lista do que foi feito — como no Claude."""
    return rx.vstack(
        rx.hstack(
            rx.icon("list-checks", size=14, color=_CINZA),
            rx.text(rx.cond(m.resumo != "", m.resumo, "Atividade"), size="2", color=_CINZA),
            _seta(m),
            align="center", spacing="2", cursor="pointer",
            on_click=AssistenteState.alternar(indice),
            _hover={"opacity": "0.75"},
        ),
        rx.cond(m.aberto, _corpo_recuado(_atividade(m))),
        spacing="2",
        align_items="stretch",
        width="100%",
    )


def _cartao(m, indice) -> rx.Component:
    """O plano (um ou mais passos), recolhido numa linha como no Claude (06/10):
    título + resumo ("2 consultas · 1 passo preparado"). Aberto, mostra a
    atividade do agente, os passos e o log completo da execução. Aviso e
    botões ficam SEMPRE à vista; rodando, uma linha diz o que está fazendo."""
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
            rx.cond(m.resumo != "", rx.text("· " + m.resumo, size="2", color=_CINZA)),
            _seta(m),
            align="center",
            spacing="2",
            cursor="pointer",
            on_click=AssistenteState.alternar(indice),
            _hover={"opacity": "0.75"},
        ),
        rx.cond(
            (m.estado == "rodando") & (AssistenteState.status_vivo != ""),
            rx.text(AssistenteState.status_vivo, size="1", color=rx.color("gray", 9),
                    padding_left="22px", white_space="nowrap", overflow="hidden",
                    text_overflow="ellipsis", width="100%"),
        ),
        rx.cond(
            m.aberto,
            _corpo_recuado(
                rx.cond(m.atividade.length() > 0, _atividade(m)),
                rx.foreach(m.passos, lambda p: _passo(m, p)),
                rx.cond(m.logs.length() > 0, _logs_guardados(m)),
            ),
        ),
        rx.vstack(
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
                rx.fragment(),
            ),
            spacing="2",
            align_items="stretch",
            padding_left="22px",  # alinhado com o título (depois do ícone)
            width="100%",
        ),
        spacing="2",
        align_items="stretch",
        width="100%",
    )


# Coluna central da conversa, como no ChatGPT: o texto não se espalha pela
# tela inteira, mas a rolagem fica na largura toda (barra encostada na borda).
_LARGURA = "860px"  # era 760px; caixa "um pouco mais comprida" (02/10)


def _arquivos(m) -> rx.Component:
    """Botões dos arquivos gerados no passo (ex.: o termo em PDF/ODT, 10/10)."""
    return rx.hstack(
        rx.foreach(
            m.arquivos,
            lambda a: rx.button(
                rx.cond(a.pasta, rx.icon("folder-open", size=14),
                        rx.cond(a.icone == "file-text", rx.icon("file-text", size=14),
                                rx.icon("file-pen-line", size=14))),
                a.rotulo,
                variant=rx.cond(a.pasta, "ghost", "soft"),
                color_scheme="gray", size="2", radius="full", cursor="pointer",
                on_click=AssistenteState.abrir_arquivo(a.caminho, a.pasta),
            ),
        ),
        spacing="2",
        wrap="wrap",
    )


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
            # Atividade ANTES do texto (como no Claude): só nas respostas
            # comuns — no cartão ela fica dentro do expansor do próprio plano.
            rx.cond((m.titulo == "") & (m.atividade.length() > 0),
                    _expansor_atividade(m, indice)),
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
            rx.cond(m.arquivos.length() > 0, _arquivos(m)),
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


def _seletor_modelo() -> rx.Component:
    """Escolha do modelo de IA, dentro da caixa de texto (como no Claude).
    Modelo sem chave aparece desabilitado; o cadastro é em Opções → API Keys.
    Sem troca automática: o pedido vai SEMPRE pelo modelo escolhido aqui."""
    return rx.select.root(
        rx.select.trigger(variant="ghost", color_scheme="gray", radius="full",
                          cursor="pointer", title="Modelo de IA",
                          # Um pouco afastado da seta (02/10).
                          margin_right="12px"),
        rx.select.content(
            rx.foreach(
                AssistenteState.modelos,
                lambda o: rx.select.item(
                    rx.cond(o.habilitado, o.rotulo, o.rotulo + " (sem chave)"),
                    value=o.id, disabled=~o.habilitado),
            ),
        ),
        value=AssistenteState.modelo,
        on_change=AssistenteState.set_modelo,
        size="2",
        disabled=AssistenteState.pensando,
    )


def _caixa_texto() -> rx.Component:
    """Cilindro com a seta na ponta direita. Enter envia; Shift+Enter quebra
    a linha e a caixa CRESCE (até ~8 linhas, depois rola) — pedido de 02/10.
    Antes era um <input> de uma linha só, que não aceitava quebra."""
    return rx.form(
        rx.hstack(
            rx.text_area(
                placeholder="Pergunte ou peça alguma coisa  (Shift+Enter quebra a linha)",
                value=AssistenteState.entrada,
                on_change=AssistenteState.set_entrada,
                disabled=AssistenteState.pensando,
                enter_key_submit=True,
                auto_height=True,
                rows="1",
                resize="none",
                size="3",
                flex="1",
                min_width="0",
                max_height="200px",
                # Sem a borda/fundo do Radix: quem desenha o cilindro é o box de fora.
                style={"box-shadow": "none", "background": "transparent",
                       "outline": "none", "font-size": "15px",
                       "padding-top": "10px", "padding-bottom": "10px"},
            ),
            _seletor_modelo(),
            rx.icon_button(
                rx.icon("arrow-up", size=16),
                type="submit",
                radius="full",
                size="3",  # círculo maior; a seta (ícone 16) continua pequena (02/10)
                # "iris": o azul puxado para o roxo da paleta do Radix.
                color_scheme="iris",
                variant="solid",
                cursor="pointer",
                flex_shrink="0",
                disabled=AssistenteState.pensando | (AssistenteState.entrada.strip() == ""),
            ),
            # "end": com várias linhas, a seta fica embaixo, ao lado da última.
            align="end",
            spacing="2",
            width="100%",
            min_height="64px",
            padding="8px 8px 8px 14px",
            border=f"1px solid {rx.color('gray', 6)}",
            # Com uma linha continua parecendo cilindro (raio = metade dos
            # 64px); ao crescer, vira uma caixa de cantos bem arredondados.
            border_radius="32px",
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
                  rx.text(AssistenteState.status_pensando, size="2", color=rx.color("gray", 11)),
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
    """Sem chave da Groq nesta máquina: o cadastro é no menu Opções → API
    Keys (02/10) — aqui só o aviso e o atalho."""
    return rx.center(
        rx.vstack(
            rx.icon("key-square", size=28, color=rx.color("gray", 10)),
            rx.text("Para usar o Assistente, cadastre a chave de um modelo (Groq ou Gemini).",
                    weight="medium", text_align="center"),
            rx.text("Menu Opções → API Keys. Cada técnico usa a sua chave.",
                    size="2", color=rx.color("gray", 10), text_align="center"),
            botao_primario("Cadastrar chave", on_click=rx.redirect(ROTA_API_KEYS)),
            spacing="3",
            align="center",
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
