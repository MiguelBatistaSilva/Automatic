"""
pages/api_keys.py — Tela "API Keys" (rota /api-keys).

Era um pop-up do menu Opções (components/dialog_api_keys.py, 02/10); virou
página em 06/10, a pedido do usuário. Continua sendo aberta SÓ pelo menu
Opções da sidebar (não tem item na navegação) — e pelo botão "Cadastrar
chave" do Assistente quando falta a chave.

Só a view; a lógica e o Cofre do Windows estão em `state/api_keys_state.py`.
"""

import reflex as rx

from state.api_keys_state import ApiKeysState
from components.layout import page_layout
from components.botoes import botao_secundario


def _secao(titulo: str, ajuda: str, placeholder: str, valor, set_valor,
           mostrar, set_mostrar, salvar, status, cor) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.text(titulo, weight="bold", size="3"),
            rx.text(ajuda, size="1", color=rx.color("gray", 10)),
            rx.input(
                placeholder=placeholder,
                type=rx.cond(mostrar, "text", "password"),
                value=valor,
                on_change=set_valor,
                width="100%",
            ),
            rx.hstack(
                rx.checkbox("Mostrar", checked=mostrar, on_change=set_mostrar, size="1"),
                rx.spacer(),
                botao_secundario("Salvar", on_click=salvar),
                width="100%",
                align="center",
            ),
            rx.text(status, color=cor, size="1"),
            spacing="2",
            align_items="stretch",
            width="100%",
        ),
        width="100%",
    )


def api_keys_page() -> rx.Component:
    s = ApiKeysState
    conteudo = rx.vstack(
        rx.heading("API Keys", size="6"),
        rx.text(
            "Chaves de serviços externos. Ficam no Cofre de Credenciais do "
            "Windows desta máquina — não vão para arquivo nem para o banco.",
            size="2",
            color=rx.color("gray", 10),
        ),
        _secao(
            "Assistente (Groq)",
            "Cada técnico usa a sua. Crie em console.groq.com → API Keys.",
            "gsk_...", s.groq, s.set_groq, s.mostrar_groq, s.set_mostrar_groq,
            s.salvar_groq, s.status_groq, s.cor_groq,
        ),
        _secao(
            "Assistente (Gemini)",
            "Opcional. Crie em aistudio.google.com → Get API key. No plano "
            "grátis o Google pode usar o que é enviado para melhorar os "
            "produtos dele.",
            "chave do Google AI Studio", s.gemini, s.set_gemini, s.mostrar_gemini,
            s.set_mostrar_gemini, s.salvar_gemini, s.status_gemini, s.cor_gemini,
        ),
        _secao(
            "Bot do Telegram",
            "Token do @BotFather. Só é preciso na máquina que roda o bot.",
            "dado pelo @BotFather", s.telegram, s.set_telegram,
            s.mostrar_telegram, s.set_mostrar_telegram,
            s.salvar_telegram, s.status_telegram, s.cor_telegram,
        ),
        spacing="4",
        width="100%",
        max_width="640px",  # formulário estreito, como as abas de Configurações
    )
    return page_layout(conteudo)
