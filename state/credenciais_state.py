"""
state/credenciais_state.py — Back-end do diálogo de Credenciais.

Reusa `services/credenciais.py`: a matrícula fica num JSON e a SENHA vai para o
Cofre de Credenciais do Windows (keyring) — nunca em disco em texto plano. É daqui
que as páginas de automação passam a obter as credenciais (`credenciais.carregar()`).

Esta é a ÚNICA state em que a senha entra numa state var (o Reflex serializa a state
ao navegador). Aceitável porque o app é local e single-user — mas é o ponto a rever
se um dia ele for servido remotamente.

O diálogo é CONTROLADO (`aberto`): quem abre é o item do menu da sidebar, que chama
`abrir` (carrega o que está salvo antes de mostrar).
"""

import reflex as rx


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
