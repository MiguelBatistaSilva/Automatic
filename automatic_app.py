"""
automatic_app.py — Ponto de entrada do app Reflex (UI única do Automatic).

Apontado por `app_module_import="automatic_app"` no rxconfig.py. Registra todas as
páginas; a estrutura (pages/, components/, states/) vive na raiz do projeto.
Credenciais e Sobre NÃO são rotas: são diálogos (pop-up) montados na sidebar —
ver `components/dialog_credenciais.py` e `components/dialog_sobre.py`.
Rode com `reflex run`. O PyQt6 foi removido — esta é a única UI.
"""

import reflex as rx

from pages.license import license_page
from pages.sla import sla_page
from pages.desmembramento import desmembramento_page, DesmembramentoState
from pages.atendimento import atendimento_page
from pages.kb import kb_page, KBState

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
