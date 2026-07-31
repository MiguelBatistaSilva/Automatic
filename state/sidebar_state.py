"""Estado da sidebar — controla expandida/contraída e destaca a rota atual.

rx.State próprio, separado dos states das páginas: cada state cuida de um assunto.
"""

import reflex as rx


class SidebarState(rx.State):
    collapsed: bool = False  # False = expandida | True = contraída

    def toggle(self):
        self.collapsed = not self.collapsed

    @rx.var
    def active_route(self) -> str:
        """A URL atual — destaca o item de menu da página em que você está.

        Normalizada: sem barra no fim e com "" virando "/", senão a raiz (Licenças)
        nunca casa com o href "/" e fica sem realce.
        """
        caminho = (self.router.page.path or "").rstrip("/")
        return caminho or "/"
