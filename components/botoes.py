"""
components/botoes.py — Os botões do app, por PAPEL.

As páginas não escolhem tamanho, cor nem variante: escolhem o que o botão FAZ.
Assim os botões ficam consistentes por construção — e mudar a altura de todos é
mexer em `TAMANHO_BOTAO` (components/theme.py), num lugar só.

Papéis:
    botao_primario    ação principal da tela  (Iniciar, Analisar SLA, Ativar)
    botao_secundario  apoio                   (Agendar, Cancelar, Fechar)
    botao_perigo      destrutivo              (Apagar, Remover, Refazer do zero)
    botao_tabela      dentro de linha de tabela, menor (Remover)
    botao_icone       só ícone, dentro de tabela (o X da agenda)

Todos repassam `**props` para o `rx.button`, então qualquer caso fora da curva
continua possível (`on_click`, `disabled`, `margin_top`, e até um `color_scheme`
próprio, como o verde do "Adicionar Base"). O que NÃO se passa por fora é o
`size` — é justamente o que estes helpers existem para centralizar.
"""

import reflex as rx

from components.theme import TAMANHO_BOTAO, TAMANHO_BOTAO_TABELA


def botao_primario(*filhos, **props) -> rx.Component:
    return rx.button(*filhos, size=TAMANHO_BOTAO, cursor="pointer", **props)


def botao_secundario(*filhos, **props) -> rx.Component:
    return rx.button(
        *filhos,
        size=TAMANHO_BOTAO,
        variant="soft",
        color_scheme="gray",
        cursor="pointer",
        **props,
    )


def botao_perigo(*filhos, **props) -> rx.Component:
    return rx.button(
        *filhos,
        size=TAMANHO_BOTAO,
        variant="soft",
        color_scheme="red",
        cursor="pointer",
        **props,
    )


def botao_tabela(*filhos, **props) -> rx.Component:
    """Botão de ação de uma linha de tabela — menor que os do formulário."""
    return rx.button(
        *filhos,
        size=TAMANHO_BOTAO_TABELA,
        variant="soft",
        color_scheme="red",
        cursor="pointer",
        **props,
    )


def botao_icone(icone: str, **props) -> rx.Component:
    """Botão só de ícone dentro de tabela (ex.: o X que remove da agenda)."""
    return botao_tabela(rx.icon(icone, size=14), **props)
