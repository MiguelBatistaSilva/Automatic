"""
pages/license.py — Aba Licencas.

E a mais simples das abas: faz login no Assyst em laco (via `_fazer_login_pw`) e
deixa o Chrome ABERTO para uso manual (`manter_aberto=True`). Foi a PoC da ponte
async<->sync com logs ao vivo — o mesmo molde vale para SLA, Desmembramento e
Atendimento.

As credenciais vem do cofre (keyring), como nas demais paginas — cadastradas no
pop-up Opcoes -> Credenciais. Nao ha mais campos de matricula/senha aqui.
"""

import reflex as rx

from states.flow_runner import FlowRunnerState
from components.log_console import log_console
from components.layout import page_layout
from components.botoes import botao_primario


class LicenseState(FlowRunnerState, rx.State):  # mixin + rx.State: logs/rodando proprios

    @rx.event(background=True)
    async def abrir_sessao(self):
        async with self:
            if self.rodando:
                return
            self.logs = []
            self.rodando = True

        # Credenciais salvas (keyring), cadastradas em Opcoes -> Credenciais.
        from services import credenciais
        matricula, senha = credenciais.carregar()
        if not matricula or not senha:
            async with self:
                self.logs = self.logs + [self._linha(
                    "Credenciais não cadastradas (menu Opções -> Credenciais).", "error")]
                self.rodando = False
            return

        def worker(log, emit):
            # Fluxo sync intacto — reusa services/browser_pw sem alteracao.
            # (Licencas so usa logs; `emit` fica disponivel mas nao e usado.)
            from services.browser_pw import NavegadorPW, _fazer_login_pw
            with NavegadorPW(log, manter_aberto=True) as page:
                _fazer_login_pw(page, matricula, senha, log)

        async for _ in self._rodar_sync(worker):
            yield

        async with self:
            self.rodando = False
        yield


def license_page() -> rx.Component:
    conteudo = rx.vstack(
        rx.heading("Licenças", size="6"),
        rx.text(
            "Faz login no Assyst quando todas as licenças estão em uso e deixa o Chrome aberto "
            "para uso manual.",
            color="#6B7280",
        ),
        botao_primario(
            "Abrir sessão",
            on_click=LicenseState.abrir_sessao,
            disabled=LicenseState.rodando,
        ),
        log_console(LicenseState.logs),
        spacing="4",
        width="100%",
    )
    return page_layout(conteudo)
