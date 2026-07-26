"""
components/form.py — Peças de layout dos formulários.

Campos dispostos SEMPRE dois a dois, em colunas de mesma largura: é o que mantém
as páginas com a mesma proporção. Nasceu no Desmembramento e passou a ser usado
também pela Análise de SLA — por isso mora aqui, e não dentro de uma página.
"""

import reflex as rx

# Altura padrão das caixas de texto grandes (descrição, CSV, lista de chamados).
# Igual em todas as páginas para as colunas fecharem alinhadas.
ALTURA_TEXTAREA = "160px"


def coluna(*filhos) -> rx.Component:
    """Uma coluna de campo que divide a largura por igual com as irmãs."""
    return rx.vstack(
        *filhos,
        spacing="1",
        align_items="stretch",
        flex="1",
        min_width="0",   # sem isto o conteúdo impede a coluna de encolher
    )


def duas_colunas(esquerda: rx.Component, direita: rx.Component) -> rx.Component:
    return rx.hstack(esquerda, direita, spacing="4", width="100%", align="start")


def meia_largura(campo: rx.Component) -> rx.Component:
    """Campo pequeno sozinho na linha: ocupa metade, o resto fica vazio."""
    return duas_colunas(campo, rx.box(flex="1"))
