"""
components/dialog_credenciais.py — Credenciais do CATI/Assyst (keyring), como POP-UP.

Era uma página/rota (`/credenciais`); virou um `rx.dialog` aberto pelo menu de opções
da sidebar — como no antigo `ui/dialog_credenciais.py` do Qt. Reusa
`services/credenciais.py`: a matrícula fica num JSON e a SENHA vai para o Cofre de
Credenciais do Windows (keyring) — nunca em disco em texto plano. É daqui que as
abas de automação passam a obter as credenciais (via `credenciais.carregar()`).

O diálogo é CONTROLADO (`aberto`): quem abre é o item do menu, que chama `abrir`
(carrega o que está salvo antes de mostrar).
"""

import reflex as rx

from components.botoes import botao_primario, botao_secundario, botao_perigo


class CredenciaisState(rx.State):
    aberto: bool = False
    matricula: str = ""
    senha: str = ""
    mostrar_senha: bool = False
    tem_salvas: bool = False
    status: str = ""
    status_cor: str = "#6B7280"

    @rx.event
    def abrir(self):
        """Carrega o que está salvo e abre o pop-up."""
        from services import credenciais
        mat, senha = credenciais.carregar()
        self.matricula = mat
        self.senha = senha
        self.mostrar_senha = False
        self.tem_salvas = bool(mat)
        self.status = ("✓ Credenciais salvas nesta máquina."
                       if mat else "Nenhuma credencial salva ainda.")
        self.status_cor = "#16A34A" if mat else "#6B7280"
        self.aberto = True

    @rx.event
    def set_aberto(self, v: bool):
        self.aberto = v

    @rx.event
    def set_matricula(self, v: str):
        self.matricula = v

    @rx.event
    def set_senha(self, v: str):
        self.senha = v

    @rx.event
    def toggle_mostrar(self, v: bool):
        self.mostrar_senha = v

    @rx.event
    def salvar(self):
        from services import credenciais
        try:
            credenciais.salvar(self.matricula, self.senha)
        except ValueError as e:
            self.status = str(e)
            self.status_cor = "#DC2626"
            return
        except Exception as e:
            self.status = f"Não foi possível gravar no Cofre do Windows: {e}"
            self.status_cor = "#DC2626"
            return
        self.tem_salvas = True
        self.status = "✓ Credenciais salvas com sucesso."
        self.status_cor = "#16A34A"

    @rx.event
    def apagar(self):
        from services import credenciais
        credenciais.apagar()
        self.matricula = ""
        self.senha = ""
        self.tem_salvas = False
        self.status = "Credenciais apagadas."
        self.status_cor = "#6B7280"


def credenciais_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Credenciais"),
            rx.dialog.description(
                "Credenciais do CATI/Assyst, usadas por todas as automações. A senha "
                "é guardada no Cofre de Credenciais do Windows, não em arquivo.",
                color="#6B7280",
                size="2",
            ),
            rx.vstack(
                rx.text("Matrícula", weight="bold", size="2"),
                rx.input(placeholder="400123", value=CredenciaisState.matricula,
                         on_change=CredenciaisState.set_matricula, width="100%"),
                rx.text("Senha", weight="bold", size="2", margin_top="0.5em"),
                rx.input(
                    placeholder="••••••",
                    type=rx.cond(CredenciaisState.mostrar_senha, "text", "password"),
                    value=CredenciaisState.senha,
                    on_change=CredenciaisState.set_senha,
                    width="100%",
                ),
                rx.checkbox("Mostrar senha", checked=CredenciaisState.mostrar_senha,
                            on_change=CredenciaisState.toggle_mostrar, size="1"),
                spacing="1",
                align_items="start",
                width="100%",
                margin_top="1em",
            ),
            rx.text(CredenciaisState.status, color=CredenciaisState.status_cor,
                    size="2", margin_top="0.75em"),
            rx.hstack(
                botao_perigo("Apagar", on_click=CredenciaisState.apagar,
                             disabled=~CredenciaisState.tem_salvas),
                rx.spacer(),
                rx.dialog.close(botao_secundario("Fechar")),
                botao_primario("Salvar", on_click=CredenciaisState.salvar),
                spacing="3",
                width="100%",
                margin_top="1.25em",
                align="center",
            ),
            max_width="420px",
        ),
        open=CredenciaisState.aberto,
        on_open_change=CredenciaisState.set_aberto,
    )
