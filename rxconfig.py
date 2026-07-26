import reflex as rx

# App Reflex do Automatic (UI única, após a saída do PyQt6).
#
# A estrutura vive na RAIZ do projeto (não num pacote `automatic_web`): o módulo de
# entrada é `automatic_app.py`, apontado por `app_module_import`. Assim `pages/`,
# `components/`, `states/` e `services/` convivem no mesmo nível e os imports
# ficam diretos (`from pages...`, `from states...`, `from services...`).
config = rx.Config(
    app_name="automatic",
    app_module_import="automatic_app",
    plugins=[rx.plugins.SitemapPlugin()],
)
