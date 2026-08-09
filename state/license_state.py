"""
state/license_state.py — Back-end da página Licenças.

É a mais simples das abas: faz login no Assyst em laço (via `_fazer_login_pw`) e
deixa o Chrome ABERTO para uso manual. Foi a PoC da ponte async<->sync com logs
ao vivo — o mesmo molde vale para SLA, Desmembramento e Atendimento.

O navegador aqui é o `NavegadorAvulsoPW`, não o `NavegadorPW` dos outros fluxos:
esta aba entrega uma JANELA, não um dado, e a janela precisa continuar usável
depois. Com o `NavegadorPW` mantido aberto, toda aba nova nascia travada (ver a
explicação em services/browser_pw.py).

As credenciais vêm do cofre (keyring), como nas demais páginas — cadastradas no
pop-up Opções -> Credenciais. Não há campos de matrícula/senha na tela.
"""

import reflex as rx

from state.flow_runner import FlowRunnerState


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
            from services.browser_pw import NavegadorAvulsoPW, _fazer_login_pw
            try:
                with NavegadorAvulsoPW(log) as page:
                    _fazer_login_pw(page, matricula, senha, log)
            except RuntimeError as e:
                # Chrome ausente ou porta ocupada: a mensagem ja explica o que
                # fazer, entao ela vale mais que um "Excecao inesperada".
                log(str(e), "error")

        async for _ in self._rodar_sync(worker):
            yield

        async with self:
            self.rodando = False
        yield
