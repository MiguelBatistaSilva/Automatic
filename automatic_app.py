"""
automatic_app.py — Ponto de entrada do app Reflex (UI única do Automatic).

Apontado por `app_module_import="automatic_app"` no rxconfig.py. Registra todas as
páginas; a estrutura (pages/, state/, components/) vive na raiz do projeto:
`pages/` só desenha, `state/` é o back-end de cada tela, `services/` é a automação
(e não importa reflex — é essa fronteira que permitiu trocar o PyQt6 pelo Reflex).
Credenciais e Sobre NÃO são rotas: são diálogos (pop-up) montados na sidebar —
ver `components/dialog_credenciais.py` e `components/dialog_sobre.py`.
Atualização não passa pela tela (desde 07/10): é o `atualizar_automatic.bat`,
com o app fechado — ver `atualizar.py`.
Rode com `reflex run`. O PyQt6 foi removido — esta é a única UI.
"""

import reflex as rx

from pages.license import license_page
from pages.sla import sla_page
from pages.desmembramento import desmembramento_page
from pages.atendimento import atendimento_page
from pages.requisicao import requisicao_page
from pages.configuracoes import configuracoes_page
from pages.meus_fluxos import meus_fluxos_page
from pages.assistente import assistente_page
from pages.api_keys import api_keys_page
from state.api_keys_state import ApiKeysState, ROTA as ROTA_API_KEYS
from state.desmembramento_state import DesmembramentoState
from state.kb_state import KBState
from state.meus_fluxos_state import MeusFluxosState
from state.assistente_state import AssistenteState
from state.requisicao_presets_state import RequisicaoPresetsState
from bot.state import TelegramState

app = rx.App(
    theme=rx.theme(accent_color="blue", gray_color="slate", radius="medium"),
    # Ícone da aba do navegador. `assets/` é servido na raiz do site, então o
    # arquivo `assets/favicon.ico` vira "/favicon.ico". É o antigo app_icon.ico,
    # que era do atalho da área de trabalho (removido junto com o PyQt6).
    head_components=[
        rx.el.link(rel="icon", type="image/x-icon", href="/favicon.ico"),
    ],
)
app.add_page(
    desmembramento_page,
    route="/desmembramento",
    title="Automatic — Desmembramento",
    on_load=DesmembramentoState.on_load,
)
app.add_page(
    atendimento_page,
    route="/atendimento",
    title="Automatic — Iniciar Atendimento",
)
app.add_page(
    requisicao_page,
    route="/requisicao",
    title="Automatic — Requisição de Serviço",
)
# Raiz = Assistente: é a página em que o app abre (decisão do usuário,
# 2026-09-30). Licenças, que era a raiz, foi para /licencas.
app.add_page(
    assistente_page,
    route="/",
    title="Automatic — Assistente",
    on_load=AssistenteState.on_load,
)
app.add_page(
    meus_fluxos_page,
    route="/meus-fluxos",
    title="Automatic — Meus fluxos",
    on_load=MeusFluxosState.on_load,
)
app.add_page(
    configuracoes_page,
    route="/configuracoes",
    title="Automatic — Configurações",
    # TelegramState.carregar_usuarios e KBState.on_load: as abas "Usuários
    # Autorizados" e "Bases de Conhecimento" migraram pra cá (ver
    # pages/configuracoes.py) — a rota /kb não existe mais.
    on_load=[RequisicaoPresetsState.on_load, TelegramState.carregar_usuarios, KBState.on_load],
)
# Sem item na navegação: abre pelo menu Opções da sidebar (era pop-up até 06/10).
app.add_page(
    api_keys_page,
    route=ROTA_API_KEYS,
    title="Automatic — API Keys",
    on_load=ApiKeysState.carregar,
)
app.add_page(
    license_page,
    route="/licencas",
    title="Automatic — Licenças",
)
app.add_page(
    sla_page,
    route="/sla",
    title="Automatic — SLA",
)
