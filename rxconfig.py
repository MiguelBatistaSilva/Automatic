import reflex as rx

# Hot-reload: o Reflex só ignora txt/json/db/log e afins; qualquer outro arquivo
# que mude dentro do projeto reinicia o backend (o app "cai"). A aba Referência
# de Configurações grava .md (e um .tmp antes) em services/agente/conhecimento/
# referencia/ — cada "Adicionar" derrubava o app (28/10). Mesma família do bug
# do .tmp do checkpoint (11/08). `.md` e `.tmp` nunca são código. A lista é
# lida na hora de subir o servidor, depois deste arquivo; se uma versão nova do
# Reflex mudar o nome, o try só deixa de ter efeito (volta a cair, não quebra).
try:
    from reflex.utils import exec as _rx_exec

    _rx_exec.HOTRELOAD_IGNORE_PATTERNS = (
        *_rx_exec.HOTRELOAD_IGNORE_PATTERNS, r"^.*\.md$", r"^.*\.tmp$")
except Exception:
    pass

# App Reflex do Automatic (UI única, após a saída do PyQt6).
#
# A estrutura vive na RAIZ do projeto (não num pacote `automatic_web`): o módulo de
# entrada é `automatic_app.py`, apontado por `app_module_import`. Assim `pages/`,
# `state/`, `components/` e `services/` convivem no mesmo nível e os imports
# ficam diretos (`from pages...`, `from state...`, `from services...`).
config = rx.Config(
    app_name="automatic",
    app_module_import="automatic_app",
    plugins=[rx.plugins.SitemapPlugin()],
)
