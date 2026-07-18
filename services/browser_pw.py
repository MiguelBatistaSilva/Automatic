"""
Camada de navegador em Playwright — piloto da migracao (fluxo SLA).

Os fluxos antigos continuam no Selenium; este modulo NAO substitui o
flow_utils.py, e sim convive com ele. Login e navegacao sao gemeos das funcoes
`_fazer_login` / `_navegar_para_chamado`, portados para a API do Playwright.

IMPORTANTE: a API sync do Playwright exige que o objeto nasca e seja usado na
MESMA thread. Por isso NAO existe singleton global aqui (ao contrario do
DriverManager): o `NavegadorPW` e criado dentro da thread do worker, via `with`.
"""

import time

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# Reaproveita as constantes/regras ja validadas no fluxo Selenium, para as duas
# implementacoes nao divergirem com o tempo.
from services.flow_utils import _URL_HOME, _URL_CHAMADO, _normalizar_id_assyst

_SEL_USERNAME = "input[name='j_username']"
_SEL_PASSWORD = "input[name='j_password']"
_SEL_LOGIN = "#loginSubmit"
_SEL_SESSAO_EXPIRADA = "ol.axios-logout-error"
_SEL_CHAMADO_CARREGADO = "#btlogEvent"


class NavegadorPW:
    """
    Abre o Chrome ja instalado na maquina (channel="chrome"), sem chromedriver.

    E justamente aqui que mora o ganho da migracao: o Playwright fala CDP direto
    com o navegador, entao nao existe binario de driver para casar de versao
    quando o Chrome atualiza sozinho.

    Uso:
        with NavegadorPW(log) as page:
            ...
    """

    def __init__(self, log_func):
        self.log = log_func
        self._pw = None
        self._browser = None
        self._context = None
        self.page = None

    def __enter__(self):
        self.log("Iniciando Chrome via Playwright (sem chromedriver)...", "info")
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            channel="chrome",
            headless=False,
            args=["--start-maximized", "--disable-infobars"],
        )
        # no_viewport: deixa a pagina ocupar a janela real, em vez do viewport
        # padrao de 1280x720 do Playwright.
        self._context = self._browser.new_context(no_viewport=True)
        self.page = self._context.new_page()
        self.log("Chrome iniciado com sucesso.", "info")
        return self.page

    def __exit__(self, exc_type, exc, tb):
        for alvo, nome in (
            (self._context, "contexto"),
            (self._browser, "navegador"),
            (self._pw, "playwright"),
        ):
            if alvo is None:
                continue
            try:
                alvo.close() if nome != "playwright" else alvo.stop()
            except Exception as e:
                self.log(f"Erro ao encerrar {nome}: {e}", "error")
        self._context = self._browser = self._pw = self.page = None
        self.log("Sessao do navegador encerrada.", "info")
        return False


def _fazer_login_pw(page, usuario: str, senha: str, log) -> bool:
    tentativa = 0
    while True:
        page.goto(_URL_HOME)
        # Mesma logica do fluxo Selenium: aguarda ate 7s o campo de usuario.
        # Se aparecer, ha tela de login. Se estourar o timeout, a sessao ja esta
        # ativa. NAO checar instantaneamente — a pagina pode nao ter renderizado
        # o campo ainda, e o login concluiria "sessao ativa" por engano (corrida).
        try:
            page.wait_for_selector(_SEL_USERNAME, timeout=7000)
        except PWTimeout:
            log("Sessao ja ativa.", "info")
            return True

        tentativa += 1
        log(f"Realizando login (tentativa {tentativa})...", "status")
        page.fill(_SEL_USERNAME, usuario)
        page.fill(_SEL_PASSWORD, senha)
        page.click(_SEL_LOGIN)
        time.sleep(3)

        if page.locator(_SEL_SESSAO_EXPIRADA).count() > 0:
            log(f"Licencas em uso, tentando novamente... (tentativa {tentativa})", "error")
            continue

        log("Login realizado com sucesso.", "success")
        return True


def _sessao_expirada_pw(page) -> bool:
    try:
        return page.locator(_SEL_SESSAO_EXPIRADA).count() > 0
    except Exception:
        return False


def _navegar_para_chamado_pw(page, numero_chamado: str, log) -> bool:
    id_final = _normalizar_id_assyst(numero_chamado)
    url = _URL_CHAMADO.format(id_final=id_final)
    log(f"Navegando para o chamado: {numero_chamado}", "status")
    # O Assyst e SPA com rota em hash: trocar window.location.href mantem a
    # aplicacao viva, enquanto um goto() recarregaria tudo do zero.
    page.evaluate("destino => window.location.href = destino", url)
    try:
        page.wait_for_selector(_SEL_CHAMADO_CARREGADO, timeout=30000)
        log("Chamado carregado!", "success")
        return True
    except PWTimeout:
        log("Reforcando carregamento...", "info")
        page.reload()
        try:
            page.wait_for_selector(_SEL_CHAMADO_CARREGADO, timeout=30000)
            log("Chamado carregado apos refresh.", "success")
            return True
        except PWTimeout as e:
            log(f"Chamado nao carregou: {e}", "error")
            return False
