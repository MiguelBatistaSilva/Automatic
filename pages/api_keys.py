"""
pages/api_keys.py — Tela "API Keys" (rota /api-keys).

Era um pop-up do menu Opções (components/dialog_api_keys.py, 02/10); virou
página em 06/10, a pedido do usuário. Continua sendo aberta SÓ pelo menu
Opções da sidebar (não tem item na navegação) — e pelo botão "Cadastrar
chave" do Assistente quando falta a chave.

Estilizada em 08/10: cartões gerados pelo catálogo (`llm.PLATAFORMAS`, ver
state/api_keys_state.py), com selo de situação, link para criar a chave e
olho para mostrar/esconder; título e subtítulo no padrão das outras páginas.

Só a view; a lógica e o Cofre do Windows estão em `state/api_keys_state.py`.
"""

import reflex as rx

from state.api_keys_state import ApiKeysState, Chave
from components.layout import page_layout
from components.botoes import botao_secundario


def _icone(c: Chave) -> rx.Component:
    """Ícone por plataforma; desconhecida (plataforma nova) cai na chave."""
    return rx.box(
        rx.match(
            c.id,
            ("groq", rx.icon("zap", size=18)),
            ("gemini", rx.icon("sparkles", size=18)),
            ("telegram", rx.icon("send", size=18)),
            rx.icon("key-round", size=18),
        ),
        display="flex", align_items="center", justify_content="center",
        width="36px", height="36px", border_radius="8px", flex_shrink="0",
        background_color=rx.color("accent", 3), color=rx.color("accent", 11),
    )


def _selo(c: Chave) -> rx.Component:
    return rx.cond(
        c.cadastrada,
        rx.badge(rx.icon("circle-check", size=12), "Cadastrada",
                 color_scheme="green", variant="soft"),
        rx.badge("Não cadastrada", color_scheme="gray", variant="soft"),
    )


def _cartao(c: Chave) -> rx.Component:
    s = ApiKeysState
    return rx.card(
        rx.vstack(
            rx.hstack(
                _icone(c),
                rx.vstack(
                    rx.text(c.nome, weight="bold", size="3"),
                    rx.text(c.usada_por, size="1", color=rx.color("gray", 10)),
                    spacing="0",
                ),
                rx.spacer(),
                _selo(c),
                width="100%",
                align="center",
            ),
            rx.hstack(
                rx.text(c.ajuda, size="1", color=rx.color("gray", 11)),
                rx.link(
                    rx.hstack(rx.text(c.link_texto, size="1"),
                              rx.icon("external-link", size=12),
                              spacing="1", align="center"),
                    href=c.link, is_external=True,
                ),
                spacing="2",
                align="center",
                wrap="wrap",
            ),
            rx.cond(
                c.aviso != "",
                rx.callout(c.aviso, icon="info", size="1", color_scheme="amber",
                           variant="surface"),
            ),
            rx.hstack(
                rx.input(
                    placeholder=c.placeholder,
                    type=rx.cond(c.mostrar, "text", "password"),
                    value=c.valor,
                    on_change=lambda v: s.set_valor(c.id, v),
                    flex="1",
                ),
                rx.icon_button(
                    rx.cond(c.mostrar, rx.icon("eye-off", size=16), rx.icon("eye", size=16)),
                    on_click=s.alternar_mostrar(c.id),
                    variant="soft", color_scheme="gray", cursor="pointer",
                    title=rx.cond(c.mostrar, "Esconder", "Mostrar"),
                ),
                botao_secundario("Salvar", on_click=s.salvar(c.id)),
                width="100%",
                align="center",
            ),
            rx.text(c.status, color=c.cor, size="1"),
            spacing="3",
            align_items="stretch",
            width="100%",
        ),
        width="100%",
    )


def _grupo(titulo: str, descricao: str, chaves) -> rx.Component:
    return rx.vstack(
        rx.heading(titulo, size="4"),
        rx.text(descricao, size="2", color="#6B7280"),
        rx.foreach(chaves, _cartao),
        spacing="3",
        width="100%",
    )


def api_keys_page() -> rx.Component:
    s = ApiKeysState
    conteudo = rx.vstack(
        rx.heading("API Keys", size="6"),
        rx.text(
            "Chaves de serviços externos. Ficam no Cofre de Credenciais do "
            "Windows desta máquina — não vão para arquivo nem para o banco.",
            color="#6B7280",
        ),
        _grupo("Assistente (IA)",
               "No chat, o técnico escolhe o modelo no seletor; só aparecem os "
               "que têm chave cadastrada.", s.ia),
        _grupo("Bot do Telegram",
               "Só na máquina que hospeda o bot.", s.bot),
        spacing="5",
        width="100%",
        max_width="640px",  # formulário estreito, como as abas de Configurações
    )
    return page_layout(conteudo)
