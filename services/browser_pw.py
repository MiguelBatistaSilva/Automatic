"""
Camada de navegador em Playwright — infraestrutura compartilhada dos fluxos.

Reune o `NavegadorPW` (abre/fecha o Chrome ja instalado, sem chromedriver) e os
helpers de pagina do Assyst usados por todos os fluxos: login, navegacao,
checagem de sessao, preenchimento de descricao e captura do numero do filho.

IMPORTANTE: a API sync do Playwright exige que o objeto nasca e seja usado na
MESMA thread. Por isso NAO existe singleton global aqui: o `NavegadorPW` e criado
dentro da thread do worker, via `with`. Os helpers SEM navegador (URLs,
normalizacao de id, montagem de descricao) vivem em `services/assyst_common.py`.
"""

import time

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# Reaproveita as constantes/regras ja validadas no fluxo Selenium, para as duas
# implementacoes nao divergirem com o tempo.
from services.assyst_common import _URL_HOME, _URL_CHAMADO, _normalizar_id_assyst

_SEL_USERNAME = "input[name='j_username']"
_SEL_PASSWORD = "input[name='j_password']"
_SEL_LOGIN = "#loginSubmit"
_SEL_SESSAO_EXPIRADA = "ol.axios-logout-error"
_SEL_CRED_INVALIDA = "ol.errormsg"
_SEL_CHAMADO_CARREGADO = "#btlogEvent"
_SEL_IFRAME_EDITOR = "iframe[title*='formattedRemarks']"


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

    def __init__(self, log_func, manter_aberto: bool = False):
        self.log = log_func
        # manter_aberto=True: sair do `with` NAO fecha o navegador. Usado pela
        # aba License, cujo proposito e justamente segurar a sessao aberta para
        # o usuario trabalhar manualmente depois — equivalente ao detach=True
        # do DriverManager no Selenium.
        #
        # Consequencia: quando a thread do worker morre, o navegador sobrevive
        # mas fica INCONTROLAVEL pelo app (a API sync do Playwright e presa a
        # thread que a criou). Quem fecha a janela e o usuario. Cada execucao
        # deixa tambem um processo do driver (node) para tras.
        self.manter_aberto = manter_aberto
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
        if self.manter_aberto:
            self.log("Navegador mantido aberto para uso manual.", "info")
            return False

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

        # Em vez de um sleep fixo de 3s apos o clique, aguardamos ATIVAMENTE o
        # desfecho: assim que o banner de "licencas em uso" aparece, a
        # retentativa dispara na hora (antes eram sempre ~3s parados a cada
        # licenca em uso, atrasando a automacao).
        desfecho = _aguardar_desfecho_login_pw(page)

        if desfecho == "licenca":
            log(f"Licencas em uso, tentando novamente... (tentativa {tentativa})", "error")
            continue

        # Credencial errada NAO pode entrar no laco infinito: repetir com a
        # mesma senha errada nunca vai logar. Sem esta checagem o Assyst apenas
        # redesenha a tela de login e a funcao concluia "sucesso" por engano —
        # o fluxo seguia adiante achando que estava logado. Isso importa mais
        # agora que a senha vem do cofre e a senha corporativa roda a cada 3
        # meses (ver dialog de Credenciais).
        if desfecho == "credencial":
            erro_cred = page.locator(_SEL_CRED_INVALIDA)
            log(f"Credencial invalida: {erro_cred.first.inner_text().strip()}", "error")
            return False

        log("Login realizado com sucesso.", "success")
        return True


def _aguardar_desfecho_login_pw(page, timeout_s: float = 8.0, intervalo_s: float = 0.15) -> str:
    """Aguarda ativamente o resultado do clique de login e retorna o desfecho.

    Substitui o antigo `time.sleep(3)` fixo. Faz polling curto e retorna assim
    que um dos tres estados for detectado, sem gastar o tempo cheio:
      - "licenca"    -> banner de licencas em uso (o chamador retenta)
      - "credencial" -> credencial invalida (o chamador aborta)
      - "sucesso"    -> tela de login sumiu (entrou)

    O teto (timeout_s) e so uma rede de seguranca: se a pagina nunca responder,
    assume "sucesso" (mesmo desfecho do fluxo antigo apos o sleep) e o proximo
    `goto` do laco reavalia a tela.
    """
    fim = time.monotonic() + timeout_s
    while time.monotonic() < fim:
        try:
            if page.locator(_SEL_SESSAO_EXPIRADA).count() > 0:
                return "licenca"
            erro_cred = page.locator(_SEL_CRED_INVALIDA)
            if erro_cred.count() > 0 and erro_cred.first.is_visible():
                return "credencial"
            # Tela de login sumiu -> navegou para a home: entrou.
            if page.locator(_SEL_USERNAME).count() == 0:
                return "sucesso"
        except Exception:
            # DOM em transicao (navegacao pos-login em curso): reavalia no
            # proximo ciclo em vez de estourar.
            pass
        time.sleep(intervalo_s)
    return "sucesso"


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


def _relogin_pw(page, numero_chamado, usuario, senha, log) -> bool:
    """Reloga e volta para o chamado (usado quando a sessao expira no meio do fluxo)."""
    log("Sessao expirada! Reconectando...", "error")
    if not _fazer_login_pw(page, usuario, senha, log):
        return False
    return _navegar_para_chamado_pw(page, numero_chamado, log)


def _capturar_numero_filho_pw(page, log) -> str:
    """Captura o numero do chamado filho gerado pelo Assyst apos salvar.

    Le o titulo do painel (h1#contentPaneTitle) e pega o primeiro token.
    """
    try:
        titulo = page.locator("h1#contentPaneTitle")
        titulo.wait_for(state="visible", timeout=10000)
        numero = titulo.inner_text().split(" ")[0].strip()
        log(f"Numero do chamado filho capturado: {numero}", "info")
        return numero
    except Exception as e:
        log(f"Nao foi possivel capturar numero do filho: {e}", "error")
        return ""


def _preencher_descricao_pw(page, log, descricao: str) -> bool:
    """
    Insere o conteudo no CKEditor do EVENTO, digitando (press_sequentially).

    Usamos frame_locator, que resolve o iframe a cada uso e ja espera por ele —
    sem risco de ficar preso num frame se algo estourar.

    Ha um unico editor 'formattedRemarks' na tela de edicao do evento; miramos o
    PRIMEIRO (`.first`). O do pop-up de acao (ultimo) e tratado a parte no
    flow_atendimento_pw. Digitar (em vez de innerHTML) atualiza o MODELO interno
    do CKEditor — foi essa a causa raiz do bug da descricao repetida em cadeia.
    Recebe TEXTO PURO (nao HTML).
    """
    try:
        editor = page.frame_locator(_SEL_IFRAME_EDITOR).first
        corpo = editor.locator("body.cke_editable")
        corpo.wait_for(state="visible", timeout=20000)

        # Foca e apaga o conteudo herdado (quando o chamado e duplicado).
        corpo.click()
        corpo.press("Control+a")
        corpo.press("Delete")

        # Digita linha a linha; cada \n vira um Enter no editor.
        linhas = descricao.split("\n")
        for i, linha in enumerate(linhas):
            if i > 0:
                corpo.press("Enter")
            if linha:
                corpo.press_sequentially(linha)

        log("Descricao preenchida com sucesso.", "success")
        return True
    except Exception as e:
        log(f"Erro ao preencher descricao: {e}", "error")
        return False
