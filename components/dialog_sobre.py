"""
components/dialog_sobre.py — "Sobre" + checagem de atualização, como POP-UP.

Era uma página/rota (`/sobre`); virou um `rx.dialog` aberto pelo menu de opções da
sidebar. Mostra a versão instalada e verifica se há versão mais nova (via
`services/update_check.verificar_atualizacao`, sem Qt). O DOWNLOAD/instalação
automática dentro do app Reflex fica para a Fase 5 (empacotamento) — por ora,
havendo versão nova, mostra o link para baixar.
"""

import asyncio

import reflex as rx

from version import VERSION
from components.botoes import botao_primario, botao_secundario

_URL_SOBRE = "https://recondite-frog-e5d.notion.site/Bem-vindo-2e6e32b25a248027b36ef626bf484553"


class SobreState(rx.State):
    aberto: bool = False
    verificando: bool = False
    status: str = ""
    status_cor: str = "#6B7280"
    url_download: str = ""

    @rx.event
    def abrir(self):
        self.status = ""
        self.status_cor = "#6B7280"
        self.url_download = ""
        self.aberto = True

    @rx.event
    def set_aberto(self, v: bool):
        self.aberto = v

    @rx.event(background=True)
    async def verificar(self):
        async with self:
            if self.verificando:
                return
            self.verificando = True
            self.status = "Verificando..."
            self.status_cor = "#6B7280"
            self.url_download = ""

        # requests é bloqueante -> roda numa thread para não travar o loop async.
        from services.update_check import verificar_atualizacao
        res = await asyncio.to_thread(verificar_atualizacao, VERSION)

        async with self:
            self.verificando = False
            if res:
                remota, url = res
                self.status = f"Nova versão disponível: v{remota}"
                self.status_cor = "#16A34A"
                self.url_download = url
            else:
                self.status = "Você está na versão mais recente."
                self.status_cor = "#6B7280"


def sobre_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Sobre"),
            rx.vstack(
                rx.text("Automatic", weight="bold", size="4"),
                rx.text(f"Versão instalada: v{VERSION}", color="#6B7280", size="2"),
                rx.link("📖  Documentação (Notion)", href=_URL_SOBRE,
                        is_external=True, size="2"),
                rx.divider(margin_y="0.5em"),
                rx.hstack(
                    botao_primario("Verificar atualização", on_click=SobreState.verificar,
                                   disabled=SobreState.verificando),
                    rx.text(SobreState.status, color=SobreState.status_cor, size="2"),
                    spacing="3",
                    align="center",
                ),
                rx.cond(
                    SobreState.url_download != "",
                    rx.link("⬇  Baixar atualização", href=SobreState.url_download,
                            is_external=True, size="2"),
                ),
                spacing="2",
                align_items="start",
                width="100%",
                margin_top="0.75em",
            ),
            rx.hstack(
                rx.spacer(),
                rx.dialog.close(botao_secundario("Fechar")),
                width="100%",
                margin_top="1.25em",
            ),
            max_width="420px",
        ),
        open=SobreState.aberto,
        on_open_change=SobreState.set_aberto,
    )
