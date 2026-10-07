"""
state/api_keys_state.py — Back-end da página "API Keys" (/api-keys, aberta
pelo menu Opções; era pop-up até 06/10).

Junta as chaves de serviços externos num lugar só (2026-10-02, pedido do
usuário): antes o token do bot tinha o pop-up "Telegram" e a chave da IA era
colada na própria página do Assistente.

  - Groq (Assistente): cada técnico cadastra a SUA — sem ela o Assistente não
    funciona. Guardada no Cofre do Windows (services/agente/llm.py).
  - Telegram (bot): o token do @BotFather, só na máquina que roda o bot
    (bot/services/credencial_servico.py).

Nenhuma chave vai para o banco, arquivo ou git. `carregar` é o on_load da
página: lê o Cofre a cada visita (outra tela pode ter mudado a chave).
"""

import reflex as rx

ROTA = "/api-keys"


class ApiKeysState(rx.State):
    groq: str = ""
    mostrar_groq: bool = False
    status_groq: str = ""
    cor_groq: str = "#6B7280"

    gemini: str = ""
    mostrar_gemini: bool = False
    status_gemini: str = ""
    cor_gemini: str = "#6B7280"

    telegram: str = ""
    mostrar_telegram: bool = False
    status_telegram: str = ""
    cor_telegram: str = "#6B7280"

    @rx.event
    def carregar(self):
        from bot.services import credencial_servico
        from services.agente import llm

        self.groq = llm.carregar_chave("groq")
        self.gemini = llm.carregar_chave("gemini")
        self.mostrar_gemini = False
        self.status_gemini = ("✓ Chave cadastrada nesta máquina." if self.gemini
                              else "Opcional: outro modelo para escolher no chat.")
        self.cor_gemini = "#16A34A" if self.gemini else "#6B7280"
        self.telegram = credencial_servico.carregar_token()
        self.mostrar_groq = self.mostrar_telegram = False
        self.status_groq = ("✓ Chave cadastrada nesta máquina." if self.groq
                            else "Sem chave: o modelo Groq fica indisponível no chat.")
        self.cor_groq = "#16A34A" if self.groq else "#B45309"
        self.status_telegram = ("✓ Token cadastrado." if self.telegram
                                else "Só é preciso na máquina que roda o bot.")
        self.cor_telegram = "#16A34A" if self.telegram else "#6B7280"

    @rx.event
    def set_groq(self, v: str):
        self.groq = v

    @rx.event
    def set_mostrar_groq(self, v: bool):
        self.mostrar_groq = v

    @rx.event
    def set_telegram(self, v: str):
        self.telegram = v

    @rx.event
    def set_mostrar_telegram(self, v: bool):
        self.mostrar_telegram = v

    @rx.event
    def salvar_groq(self):
        from services.agente import llm

        chave = self.groq.strip()
        if not chave.startswith("gsk_"):
            self.status_groq = "A chave da Groq começa com gsk_ — confira o que foi colado."
            self.cor_groq = "#DC2626"
            return
        try:
            llm.salvar_chave(chave, "groq")
        except Exception as e:
            self.status_groq = f"Não foi possível gravar no Cofre do Windows: {e}"
            self.cor_groq = "#DC2626"
            return
        self.status_groq = "✓ Chave salva. O Assistente já pode ser usado."
        self.cor_groq = "#16A34A"
        # A página do Assistente (se aberta) passa a mostrar o chat na hora.
        from state.assistente_state import AssistenteState
        return AssistenteState.on_load

    @rx.event
    def set_gemini(self, v: str):
        self.gemini = v

    @rx.event
    def set_mostrar_gemini(self, v: bool):
        self.mostrar_gemini = v

    @rx.event
    def salvar_gemini(self):
        from services.agente import llm

        # Sem trava de prefixo: o Google tem mais de um formato de chave (a do
        # usuário começa com "AQ.", não "AIza" — 02/10). Quem confere de
        # verdade é a primeira chamada ao modelo.
        chave = self.gemini.strip()
        if not chave:
            self.status_gemini = "Cole a chave antes de salvar."
            self.cor_gemini = "#DC2626"
            return
        try:
            llm.salvar_chave(chave, "gemini")
        except Exception as e:
            self.status_gemini = f"Não foi possível gravar no Cofre do Windows: {e}"
            self.cor_gemini = "#DC2626"
            return
        self.status_gemini = "✓ Chave salva. O Gemini já aparece no seletor do chat."
        self.cor_gemini = "#16A34A"
        from state.assistente_state import AssistenteState
        return AssistenteState.on_load

    @rx.event
    def salvar_telegram(self):
        from bot.services import credencial_servico

        try:
            credencial_servico.salvar_token(self.telegram)
        except ValueError as e:
            self.status_telegram, self.cor_telegram = str(e), "#DC2626"
            return
        except Exception as e:
            self.status_telegram = f"Não foi possível gravar no Cofre do Windows: {e}"
            self.cor_telegram = "#DC2626"
            return
        self.status_telegram, self.cor_telegram = "✓ Token salvo.", "#16A34A"
