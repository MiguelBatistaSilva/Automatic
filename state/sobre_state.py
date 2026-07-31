"""
state/sobre_state.py — Back-end do diálogo "Sobre".

Só abre e fecha: a checagem de atualização foi RETIRADA em 2026-07-27, quando a
distribuição passou a ser manual (baixar o zip do GitHub e rodar o
`iniciar_automatic.bat`). Saíram junto o `version.py`, o `version.json` e o
`services/update_check.py`.
"""

import reflex as rx


class SobreState(rx.State):
    aberto: bool = False

    @rx.event
    def abrir(self):
        self.aberto = True

    @rx.event
    def set_aberto(self, v: bool):
        self.aberto = v
