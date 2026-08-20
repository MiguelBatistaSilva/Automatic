"""
automatic_app.py — Ponto de entrada do app Reflex (UI única do Automatic).

Apontado por `app_module_import="automatic_app"` no rxconfig.py. Registra todas as
páginas; a estrutura (pages/, state/, components/) vive na raiz do projeto:
`pages/` só desenha, `state/` é o back-end de cada tela, `services/` é a automação
(e não importa reflex — é essa fronteira que permitiu trocar o PyQt6 pelo Reflex).
Credenciais e Sobre NÃO são rotas: são diálogos (pop-up) montados na sidebar —
ver `components/dialog_credenciais.py` e `components/dialog_sobre.py`.
`senior/` é à parte: automação da Senior HCM (Ponto), site/credencial diferentes
do Assyst — page/state/service/credenciais próprios, sem entrada na sidebar
(components/sidebar.py NAV_ITEMS), só a rota /ponto mesmo.
Atualização (ícone na topbar, components/topbar.py — acima do conteúdo, separada
da sidebar) também não é rota: verificar/baixar rodam aqui dentro
(state/update_state.py), mas quem troca os arquivos de fato é `atualizar.py` na
raiz, sempre com o app fechado — ver o docstring de lá.
Rode com `reflex run`. O PyQt6 foi removido — esta é a única UI.
"""

import reflex as rx

from pages.license import license_page
from pages.sla import sla_page
from pages.desmembramento import desmembramento_page
from pages.atendimento import atendimento_page
from pages.requisicao import requisicao_page
from pages.kb import kb_page
from senior.page import ponto_page
from state.desmembramento_state import DesmembramentoState
from state.kb_state import KBState
from senior.state import PontoState

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
app.add_page(
    kb_page,
    route="/kb",
    title="Automatic — Bases de Conhecimento",
    on_load=KBState.on_load,
)
app.add_page(
    license_page,
    route="/",
    title="Automatic — Licenças",
)
app.add_page(
    sla_page,
    route="/sla",
    title="Automatic — SLA",
)
app.add_page(
    ponto_page,
    route="/ponto",
    title="Automatic — Ponto",
    on_load=PontoState.on_load,
)
