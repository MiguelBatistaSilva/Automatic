"""
pages/plantoes.py — Tela "Plantões Judiciários" (18/11).

Um acordeão por local (Sede, Fórum, Custódia, cada um com a sua fila); dentro,
os dias lado a lado, cada um com o técnico. O Sentinela (services/plantoes.py) cria as Requisições
quando a escala fica completa. O back-end está em state/plantoes_state.py.
"""

import reflex as rx

from components.botoes import botao_primario, botao_secundario
from components.layout import page_layout
from components.theme import TAMANHO_BOTAO
from services import plantoes
from state.plantoes_state import PlantoesState


def _dia(l: rx.Var) -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.text(l.rotulo, weight="bold"),
                rx.spacer(),
                rx.cond(
                    l.aviso != "",
                    rx.tooltip(rx.icon("triangle-alert", size=16, color="orange"),
                               content=l.aviso),
                ),
                align="center",
                width="100%",
            ),
            rx.select(
                PlantoesState.tecnicos,
                value=l.tecnico,
                placeholder="Escolha o técnico",
                on_change=lambda v: PlantoesState.definir(l.local, l.dia, "tecnico", v),
                disabled=PlantoesState.travada,
                width="100%",
            ),
            spacing="1",
            width="100%",
        ),
        flex="1 1 0",
        min_width="220px",
    )


def _situacao(chave: str) -> rx.Component:
    falta = PlantoesState.pendente[chave]
    return rx.cond(
        falta == "",
        rx.tooltip(rx.icon("circle-check", size=18, color="green"), content="Tudo preenchido."),
        rx.tooltip(
            rx.badge(rx.icon("clock", size=12), "Pendente", color_scheme="orange", variant="soft"),
            content=falta,
        ),
    )


def _local(chave: str, nome: str, horario: str, fila: str) -> rx.Component:
    return rx.accordion.item(
        header=rx.hstack(
            rx.text(nome, weight="bold"),
            rx.text(horario.replace(" as ", " às "), size="2", color="#6B7280"),
            rx.badge(fila, variant="soft", color_scheme="gray"),
            rx.spacer(),
            _situacao(chave),
            spacing="3",
            align="center",
            width="100%",
            padding_right="0.5em",
        ),
        content=rx.flex(
            rx.foreach(
                PlantoesState.linhas,
                lambda l: rx.cond(l.local == chave, _dia(l), rx.fragment()),
            ),
            spacing="3",
            wrap="wrap",
            width="100%",
            padding_y="0.5em",
        ),
        value=chave,
    )


def _dias() -> rx.Component:
    return rx.hstack(
        rx.text("Dias do plantão", weight="bold"),
        rx.foreach(
            PlantoesState.dias,
            lambda d: rx.badge(
                d.rotulo,
                rx.cond(
                    PlantoesState.travada | d.fixo,
                    rx.fragment(),
                    rx.icon("x", size=12, cursor="pointer",
                            on_click=PlantoesState.remover_dia(d.dia)),
                ),
                size="2", variant="soft",
            ),
        ),
        spacing="2",
        align="center",
        wrap="wrap",
    )


def _feriados_extras() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.trigger(botao_secundario(rx.icon("calendar-plus", size=16), "Adicionar dias")),
        rx.dialog.content(
            rx.dialog.title("Adicionar dias"),
            rx.dialog.description(
                "Feriado colado no fim de semana (nacional, Páscoa, Ceará, Fortaleza) já "
                "entra sozinho. Cadastre aqui os outros: feriado no meio da semana, "
                "portaria do TJCE, ponto facultativo. Colado no fim de semana, entra "
                "nele; no meio da semana, entra na escala do sábado anterior.",
                size="2",
            ),
            rx.vstack(
                rx.hstack(
                    rx.foreach(
                        PlantoesState.extras,
                        lambda x: rx.badge(
                            x.rotulo,
                            rx.icon("x", size=12, cursor="pointer",
                                    on_click=PlantoesState.remover_extra(x.dia)),
                            size="2", variant="soft", color_scheme="gray",
                        ),
                    ),
                    spacing="2",
                    wrap="wrap",
                ),
                rx.hstack(
                    rx.input(type="date", value=PlantoesState.extra_dia,
                             on_change=PlantoesState.set_extra_dia, width="160px"),
                    rx.input(placeholder="Nome (opcional, ex.: Ponto facultativo)",
                             value=PlantoesState.extra_nome,
                             on_change=PlantoesState.set_extra_nome, flex="1"),
                    botao_primario("Cadastrar", on_click=PlantoesState.adicionar_extra),
                    spacing="2",
                    width="100%",
                ),
                rx.hstack(
                    rx.spacer(),
                    rx.dialog.close(botao_secundario("Fechar")),
                    width="100%",
                ),
                spacing="3",
                width="100%",
                margin_top="1em",
            ),
            max_width="560px",
        ),
    )


def _topo() -> rx.Component:
    return rx.hstack(
        rx.heading("Plantões Judiciários", size="6"),
        align="center",
        spacing="2",
        width="100%",
        wrap="wrap",
    )


def _sentinela() -> rx.Component:
    return rx.card(
        rx.vstack(
            rx.hstack(
                rx.button(
                    rx.icon("shield", size=16),
                    rx.cond(PlantoesState.ligado, "Sentry Mode: ligado", "Sentry Mode"),
                    on_click=PlantoesState.alternar,
                    size=TAMANHO_BOTAO,
                    variant=rx.cond(PlantoesState.ligado, "solid", "soft"),
                    color_scheme=rx.cond(PlantoesState.ligado, "green", "gray"),
                    cursor="pointer",
                ),
                botao_secundario("Atualizar", on_click=PlantoesState.carregar),
                _feriados_extras(),
                rx.cond(PlantoesState.info != "", rx.text(PlantoesState.info, size="2")),
                align="center",
                spacing="2",
                width="100%",
                wrap="wrap",
            ),
            rx.hstack(
                rx.text("Inicia às:", size="2"),
                rx.input(type="time", value=PlantoesState.hora_hora,
                         on_change=PlantoesState.set_hora_hora,
                         on_blur=PlantoesState.salvar_hora, width="110px"),
                rx.text("na véspera do 1º dia (", PlantoesState.inicio, ")",
                        size="2", color="#6B7280"),
                align="center",
                spacing="2",
                wrap="wrap",
            ),
            rx.cond(
                PlantoesState.resumo != "",
                rx.box(rx.markdown(PlantoesState.resumo), width="100%"),
            ),
            rx.cond(
                PlantoesState.fase == plantoes.ERRO,
                botao_primario("Tentar de novo", on_click=PlantoesState.tentar_de_novo),
            ),
            rx.cond(
                (PlantoesState.fase == plantoes.CONCLUIDO) | (PlantoesState.fase == plantoes.ERRO),
                botao_secundario("Nova escala (próximo fim de semana)",
                                 on_click=PlantoesState.nova_escala),
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )


def plantoes_page() -> rx.Component:
    conteudo = rx.vstack(
        _topo(),
        rx.text(
            "Escolha o técnico de cada local em cada dia (a fila é a do local). Com o Sentry Mode "
            "ligado, as Requisições do plantão são criadas na véspera do 1º dia, no horário "
            "marcado. Se a escala estiver incompleta, avisa e inicia assim que completar.",
            color="#6B7280",
        ),
        _sentinela(),
        rx.hstack(
            rx.text("Matrícula do supervisor (usuário afetado)", weight="bold"),
            rx.input(value=PlantoesState.supervisor, on_change=PlantoesState.set_supervisor,
                     on_blur=PlantoesState.salvar_supervisor, width="140px",
                     disabled=PlantoesState.travada),
            rx.cond(
                PlantoesState.falta != "",
                rx.badge(rx.icon("clock", size=12), "Pendente", color_scheme="orange", variant="soft"),
            ),
            align="center",
            spacing="3",
        ),
        _dias(),
        rx.accordion.root(
            *[_local(chave, nome, horario, fila) for chave, nome, _, _, horario, fila in plantoes.LOCAIS],
            type="multiple",
            default_value=[c for c, *_ in plantoes.LOCAIS],
            collapsible=True,
            width="100%",
            variant="outline",
        ),
        spacing="4",
        width="100%",
    )
    return page_layout(conteudo)
