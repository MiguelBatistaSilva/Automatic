"""
bot/state.py — Back-end do diálogo "Telegram" (menu de opções) e da aba
"Usuários Autorizados" na página Configurações.

Token do bot (@BotFather) e a whitelist de chat_ids. Motivo de virar tela: se
quem normalmente cadastra não puder, outro colega faz na própria máquina, sem
precisar abrir terminal.

A whitelist saiu do diálogo (2026-09-09) e foi para a página Configurações
(antes "Presets da Requisição") — as duas são config exclusiva do bot, faz
mais sentido ficarem juntas do que uma no pop-up e outra numa página. O
diálogo ficou só com o token; por isso `abrir()` (chamada por ele) e
`carregar_usuarios()` (chamada pelo `on_load` daquela página) carregam
coisas diferentes.

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
    aberto: bool = False

    token: str = ""
    mostrar_token: bool = False
    tem_token: bool = False

    usuarios: list[tuple[str, str]] = []
    novo_chat_id: str = ""
    novo_nome: str = ""

    status: str = ""
    status_cor: str = "#6B7280"

    @rx.event
    def abrir(self):
        """Carrega o token e abre o pop-up. A whitelist de usuários não mora
        mais aqui (ver `carregar_usuarios`) — foi para a página Presets da
        Requisição, junto do resto do que é config específica do bot."""
        from bot.services import credencial_servico

        self.token = credencial_servico.carregar_token()
        self.mostrar_token = False
        self.tem_token = bool(self.token)

        self.status = ""
        self.status_cor = "#6B7280"
        self.aberto = True

    @rx.event
    def carregar_usuarios(self):
        """on_load da página Configurações — carrega a whitelist sem abrir o
        pop-up do Telegram (que agora só cuida do token)."""
        from bot import usuarios

        self.usuarios = sorted(usuarios.listar().items())
        self.novo_chat_id = ""
        self.novo_nome = ""

    @rx.event
    def set_aberto(self, v: bool):
        self.aberto = v

    @rx.event
    def set_token(self, v: str):
        self.token = v

    @rx.event
    def toggle_mostrar_token(self, v: bool):
        self.mostrar_token = v

    @rx.event
    def set_novo_chat_id(self, v: str):
        self.novo_chat_id = v

    @rx.event
    def set_novo_nome(self, v: str):
        self.novo_nome = v

    @rx.event
    def salvar_token(self):
        from bot.services import credencial_servico

        try:
            credencial_servico.salvar_token(self.token)
        except ValueError as e:
            self.status = str(e)
            self.status_cor = "#DC2626"
            return
        except Exception as e:
            self.status = f"Não foi possível gravar no Cofre do Windows: {e}"
            self.status_cor = "#DC2626"
            return
        self.tem_token = True
        self.status = "✓ Token salvo com sucesso."
        self.status_cor = "#16A34A"

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
