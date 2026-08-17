"""
pages/desmembramento.py — Tela da aba "Desmembramento" (3 modos).

Só a view: o seletor de modo, os painéis de cada modo, o diálogo de checkpoint e o
console de logs. O back-end (os 3 fluxos, a validação e a decisão do checkpoint)
está em `state/desmembramento_state.py`.
"""

import reflex as rx

from state.desmembramento_state import DesmembramentoState
from components.log_console import log_console
from components.layout import page_layout
from components.form import coluna, duas_colunas, meia_largura, ALTURA_TEXTAREA
from components.botoes import botao_primario, botao_secundario


def _ajuda_marcadores() -> rx.Component:
    return rx.text(
        "Use marcadores {{COLUNA}} na descrição — são trocados pelos valores de "
        "cada linha do CSV (a 1ª linha do CSV é o cabeçalho com os nomes das colunas).",
        color="#6B7280",
        size="1",
    )


def _bloco_exemplo(rotulo: str, texto: str) -> rx.Component:
    """Um bloco de exemplo (rótulo + caixa monoespaçada) — mesmo estilo usado nos
    exemplos da Requisição de Serviço (`pages/requisicao.py::_exemplos`)."""
    return rx.vstack(
        rx.text(rotulo, size="1", weight="bold", color=rx.color("gray", 11)),
        rx.box(
            rx.text(
                texto,
                size="1",
                font_family="monospace",
                white_space="pre-wrap",
                color=rx.color("gray", 12),
            ),
            width="100%",
            padding="0.5em 0.7em",
            border=f"1px solid {rx.color('gray', 6)}",
            border_radius="6px",
            background=rx.color("gray", 2),
        ),
        spacing="1",
        width="100%",
        align_items="stretch",
    )


def _exemplo_desmembramento() -> rx.Component:
    """Pop-up com um exemplo completo: como o CSV e a Descrição se combinam via
    marcadores `{{COLUNA}}`. Mesmo padrão do pop-up de regras das filas na
    Análise de SLA (`pages/sla.py::_regras_das_filas`) — ícone de info ao lado
    do rótulo onde a dúvida aparece (aqui, 'Descrição').
    """
    return rx.popover.root(
        rx.popover.trigger(
            rx.button(
                rx.icon("info", size=14),
                size="1",
                variant="ghost",
                color_scheme="gray",
                cursor="pointer",
                title="Exemplo de preenchimento",
            ),
        ),
        rx.popover.content(
            rx.vstack(
                rx.text("Como o CSV vira a Descrição", weight="bold", size="2"),
                rx.text(
                    "A 1ª linha do CSV é o cabeçalho, com os nomes das colunas. "
                    "Cada linha seguinte vira UM chamado filho. Na Descrição, os "
                    "marcadores {{COLUNA}} são trocados pelo valor daquela coluna "
                    "na linha do momento.",
                    size="1",
                    color=rx.color("gray", 11),
                ),
                _bloco_exemplo(
                    "Dados de Iteração (CSV)",
                    "Marca,Tombo\nPOSITIVO C6200,212150\nHP ProBook 450,198342",
                ),
                _bloco_exemplo(
                    "Descrição",
                    "Solicito troca do equipamento {{Marca}}, tombo {{Tombo}}, "
                    "por apresentar defeito.",
                ),
                rx.text(
                    "Vira, no 1º chamado filho:",
                    size="1", color=rx.color("gray", 11), margin_top="0.2em",
                ),
                _bloco_exemplo(
                    "Resultado (linha 1)",
                    "Solicito troca do equipamento POSITIVO C6200, tombo 212150, "
                    "por apresentar defeito.",
                ),
                spacing="2",
                align_items="stretch",
            ),
            width="480px",
            max_width="90vw",
        ),
    )


def _campo_descricao() -> rx.Component:
    return coluna(
        rx.hstack(
            rx.text("Descrição", weight="bold"),
            _exemplo_desmembramento(),
            align="center",
            spacing="2",
        ),
        rx.text_area(
            value=DesmembramentoState.descricao,
            on_change=DesmembramentoState.set_descricao,
            height=ALTURA_TEXTAREA,
            width="100%",
            font_family="monospace",
        ),
        _ajuda_marcadores(),
    )


def _campo_chamado() -> rx.Component:
    return coluna(
        rx.text("Referência", weight="bold"),
        rx.input(
            placeholder="Ex: S2123456",
            value=DesmembramentoState.chamado_pai,
            on_change=DesmembramentoState.set_chamado_pai,
            width="100%",
        ),
    )


def _campo_kb() -> rx.Component:
    return coluna(
        rx.text("Base de Conhecimento", weight="bold"),
        rx.select(
            DesmembramentoState.kbs,
            value=DesmembramentoState.kb_selecionado,
            on_change=DesmembramentoState.set_kb,
            placeholder="Selecione a Base",
            width="100%",
        ),
    )


def _campo_csv() -> rx.Component:
    return coluna(
        rx.text("Dados de Iteração (CSV)", weight="bold"),
        rx.text_area(
            placeholder="Marca,Tombo\nPOSITIVO C6200,212150\nHP ProBook 450,198342",
            value=DesmembramentoState.csv_texto,
            on_change=DesmembramentoState.set_csv_texto,
            height=ALTURA_TEXTAREA,
            width="100%",
            font_family="monospace",
        ),
    )


def _campo_filhos() -> rx.Component:
    return coluna(
        rx.text("Chamados (um por linha)", weight="bold"),
        rx.text_area(
            placeholder="S2198432\nS2198433\nS2198434",
            value=DesmembramentoState.filhos_texto,
            on_change=DesmembramentoState.set_filhos_texto,
            height=ALTURA_TEXTAREA,
            width="100%",
            font_family="monospace",
        ),
    )


# Layout dos painéis: campos curtos numa linha, campos grandes noutra — sempre
# dois a dois, para as colunas ficarem na mesma proporção em todos os modos.
def _painel_completo() -> rx.Component:
    return rx.vstack(
        duas_colunas(_campo_chamado(), _campo_kb()),
        duas_colunas(_campo_descricao(), _campo_csv()),
        spacing="4", width="100%",
    )


def _painel_criar() -> rx.Component:
    return rx.vstack(
        meia_largura(_campo_chamado()),
        duas_colunas(_campo_descricao(), _campo_csv()),
        spacing="4", width="100%",
    )


def _painel_bc() -> rx.Component:
    return rx.vstack(
        meia_largura(_campo_kb()),
        duas_colunas(_campo_filhos(), rx.box(flex="1")),
        spacing="4", width="100%",
    )


def _dialog_checkpoint() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Checkpoint encontrado"),
            rx.cond(
                DesmembramentoState.cp_modo == "concluido",
                rx.vstack(
                    rx.text("O chamado ", rx.text.strong(DesmembramentoState.cp_label),
                            " já foi totalmente processado."),
                    rx.text("Deseja executar novamente do zero?"),
                    rx.hstack(
                        botao_primario("Refazer do zero", on_click=DesmembramentoState.cp_do_zero),
                        botao_secundario("Cancelar", on_click=DesmembramentoState.cp_cancelar),
                        spacing="3", margin_top="0.5em",
                    ),
                    spacing="2",
                ),
                rx.vstack(
                    rx.text("Execução anterior incompleta de ",
                            rx.text.strong(DesmembramentoState.cp_label), ":"),
                    rx.text(DesmembramentoState.cp_resumo, color="#D97706"),
                    rx.hstack(
                        botao_primario("Retomar", on_click=DesmembramentoState.cp_retomar),
                        botao_secundario("Começar do zero", on_click=DesmembramentoState.cp_do_zero),
                        botao_secundario("Cancelar", on_click=DesmembramentoState.cp_cancelar),
                        spacing="3", margin_top="0.5em",
                    ),
                    spacing="2",
                ),
            ),
        ),
        open=DesmembramentoState.cp_aberto,
    )


def desmembramento_page() -> rx.Component:
    conteudo = rx.vstack(
        rx.heading("Desmembramento", size="6"),
        rx.text(
            "Desmembra chamados a partir de uma referência e adiciona a Base de Conhecimento a eles.",
            color="#6B7280",
            max_width="820px",
        ),
        # Só desenha o formulário depois que o estado do backend chega. Sem isto o
        # navegador renderiza com o valor PADRAO do `modo` ("completo") e troca para
        # o modo real logo em seguida — o pisca de aba ao atualizar a página.
        rx.cond(
            DesmembramentoState.is_hydrated,
            rx.vstack(
                rx.segmented_control.root(
                    rx.segmented_control.item("Criar + Base", value="completo"),
                    rx.segmented_control.item("Só Criar", value="criar"),
                    rx.segmented_control.item("Só Base", value="bc"),
                    value=DesmembramentoState.modo,
                    on_change=DesmembramentoState.set_modo,
                ),
                rx.match(
                    DesmembramentoState.modo,
                    ("completo", _painel_completo()),
                    ("criar", _painel_criar()),
                    ("bc", _painel_bc()),
                    _painel_completo(),
                ),
                botao_primario(
                    "Iniciar",
                    on_click=DesmembramentoState.iniciar,
                    disabled=DesmembramentoState.rodando,
                ),
                spacing="4",
                width="100%",
            ),
            # Mesma altura aproximada do formulário, para a página não pular.
            rx.center(rx.spinner(size="3"), height="380px", width="100%"),
        ),
        rx.heading("Registro de Execução", size="4", margin_top="0.5em"),
        log_console(DesmembramentoState.logs),
        _dialog_checkpoint(),
        spacing="4",
        width="100%",   # sem max_width: os campos e o log ocupam a página toda
    )
    return page_layout(conteudo)
