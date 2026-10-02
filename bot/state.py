"""
bot/state.py — Back-end da aba "Usuários Autorizados" na página Configurações
(a whitelist de chat_ids do bot).

O TOKEN do bot saiu daqui em 2026-10-02: o pop-up "Telegram" virou "API
Keys" (state/api_keys_state.py), junto da chave da Groq do Assistente.

NÃO cadastra mais credencial do Assyst aqui — desde 2026-08-26 cada pessoa
cadastra a PRÓPRIA matrícula/senha direto no bot, com /credencial (ver
`bot/commands/cmd_credencial.py`). Fazia sentido ter uma tela pra isso quando havia UMA
credencial só para todo mundo; com credencial por pessoa, quem cadastra tem
que ser a própria pessoa, então só faz sentido pelo chat dela com o bot.

Cofre e arquivos são os do BOT (`bot/services/credencial_servico.py`, `bot/usuarios.py`
— serviço "Automatic-Bot" no keyring), de propósito separados do
`CredenciaisState` (cofre "Automatic", a matrícula pessoal de quem usa o app).
Misturar os dois aqui recriaria o risco que motivou separar os cofres.
"""

import reflex as rx


class TelegramState(rx.State):
    usuarios: list[tuple[str, str]] = []
    novo_chat_id: str = ""
    novo_nome: str = ""

    status: str = ""
    status_cor: str = "#6B7280"

    @rx.event
    def carregar_usuarios(self):
        """on_load da página Configurações — carrega a whitelist sem abrir o
        pop-up do Telegram (que agora só cuida do token)."""
        from bot import usuarios

        self.usuarios = sorted(usuarios.listar().items())
        self.novo_chat_id = ""
        self.novo_nome = ""

    @rx.event
    def set_novo_chat_id(self, v: str):
        self.novo_chat_id = v

    @rx.event
    def set_novo_nome(self, v: str):
        self.novo_nome = v

    @rx.event
    def adicionar_usuario(self):
        from bot import usuarios

        chat_id = self.novo_chat_id.strip()
        nome = self.novo_nome.strip()
        if not chat_id.isdigit():
            self.status = "chat_id inválido — só números."
            self.status_cor = "#DC2626"
            return
        if not nome:
            self.status = "Informe um nome/apelido."
            self.status_cor = "#DC2626"
            return

        usuarios.cadastrar(int(chat_id), nome)
        self.usuarios = sorted(usuarios.listar().items())
        self.novo_chat_id = ""
        self.novo_nome = ""
        self.status = f"✓ {nome} liberado(a) para usar o bot."
        self.status_cor = "#16A34A"

    @rx.event
    def remover_usuario(self, chat_id: str):
        from bot import usuarios

        usuarios.remover(chat_id)
        self.usuarios = sorted(usuarios.listar().items())
        self.status = "Usuário removido da lista."
        self.status_cor = "#6B7280"
