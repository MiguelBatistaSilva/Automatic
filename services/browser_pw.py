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

# Respiro entre retentativas de login. Existe para nao martelar o Assyst em laco
# apertado quando as licencas estao esgotadas (o fluxo Selenium tinha o mesmo
# 0.5s). Curto de proposito: a aba Licencas ganha a licenca de quem estiver
# tentando primeiro, entao ficar lento aqui custa a licenca.
_PAUSA_ENTRE_TENTATIVAS_S = 0.5

# Quantos polls consecutivos sem o campo de usuario confirmam que entramos.
# Com intervalo_s=0.15 -> ~0.6s de ausencia sustentada.
_POLLS_CONFIRMA_SUCESSO = 4


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
    """Insiste no login ate entrar. Só desiste se a CREDENCIAL estiver errada.

    O laco e infinito de proposito (aba Licencas): quando todas as licencas do
    Assyst estao em uso, a unica saida e retentar ate alguem sair. Por isso
    NENHUMA falha tecnica pode escapar daqui — um PWTimeout no `goto`/`fill`
    subindo pela pilha mata a thread do worker e o app aparenta ter um "limite
    de tentativas" (era o que acontecia: o Assyst engasga justamente quando esta
    saturado, que e exatamente quando este laco precisa insistir).
    """
    tentativa = 0
    while True:
        try:
            page.goto(_URL_HOME)
        except PWTimeout:
            log("A home nao respondeu; tentando novamente...", "error")
            time.sleep(_PAUSA_ENTRE_TENTATIVAS_S)
            continue

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
        try:
            page.fill(_SEL_USERNAME, usuario)
            page.fill(_SEL_PASSWORD, senha)
            page.click(_SEL_LOGIN)
        except PWTimeout:
            log(f"Tela de login travou; tentando novamente... (tentativa {tentativa})", "error")
            time.sleep(_PAUSA_ENTRE_TENTATIVAS_S)
            continue

        # Em vez de um sleep fixo de 3s apos o clique, aguardamos ATIVAMENTE o
        # desfecho: assim que o banner de "licencas em uso" aparece, a
        # retentativa dispara na hora (antes eram sempre ~3s parados a cada
        # licenca em uso, atrasando a automacao).
        desfecho = _aguardar_desfecho_login_pw(page)

        # Credencial errada NAO pode entrar no laco infinito: repetir com a
        # mesma senha errada nunca vai logar. Sem esta checagem o Assyst apenas
        # redesenha a tela de login e a funcao concluia "sucesso" por engano —
        # o fluxo seguia adiante achando que estava logado. Isso importa mais
        # agora que a senha vem do cofre e a senha corporativa roda a cada 3
        # meses (ver dialog de Credenciais).
        if desfecho == "credencial":
            erro_cred = page.locator(_SEL_CRED_INVALIDA)
            try:
                detalhe = erro_cred.first.inner_text().strip()
            except Exception:
                detalhe = "verifique matricula e senha em Opcoes -> Credenciais"
            log(f"Credencial invalida: {detalhe}", "error")
            return False

        if desfecho == "sucesso":
            log("Login realizado com sucesso.", "success")
            return True

        if desfecho == "licenca":
            log(f"Licencas em uso, tentando novamente... (tentativa {tentativa})", "error")
        else:
            # "indefinido": a pagina nao se decidiu no tempo previsto. Retentar e
            # SEMPRE seguro — se na verdade tinha entrado, o `goto` do proximo
            # ciclo cai na home e o wait_for_selector conclui "Sessao ja ativa".
            log(f"Login sem desfecho claro; tentando novamente... (tentativa {tentativa})", "info")

        time.sleep(_PAUSA_ENTRE_TENTATIVAS_S)


def _aguardar_desfecho_login_pw(page, timeout_s: float = 10.0, intervalo_s: float = 0.15) -> str:
    """Aguarda ativamente o resultado do clique de login e retorna o desfecho.

    Substitui o antigo `time.sleep(3)` fixo. Faz polling curto e retorna assim
    que um dos estados for detectado, sem gastar o tempo cheio:
      - "licenca"    -> banner de licencas em uso (o chamador retenta)
      - "credencial" -> credencial invalida (o chamador aborta)
      - "sucesso"    -> tela de login sumiu e CONTINUOU sumida (entrou)
      - "indefinido" -> estourou o teto sem conclusao (o chamador retenta)

    CORRIDA QUE CUSTOU CARO: "tela de login sumiu" NAO pode ser julgado num unico
    poll. O clique de login navega, e durante a troca de documento o campo de
    usuario momentaneamente nao existe no DOM — o antigo `count() == 0` lia isso
    como sucesso e o laco de retentativa terminava ANTES de logar, com a mensagem
    "Login realizado com sucesso" numa tela de login. Agora a ausencia precisa se
    SUSTENTAR por `_POLLS_CONFIRMA_SUCESSO` ciclos: se a pagina que chega e a de
    login de novo (com o banner de licencas), o contador zera e o banner e visto.

    O teto tambem nao mente mais: antes retornava "sucesso" ao estourar, o que
    encerrava o laco por engano. Agora devolve "indefinido" e quem chama retenta.
    """
    fim = time.monotonic() + timeout_s
    ausencias = 0
    while time.monotonic() < fim:
        try:
            erro_cred = page.locator(_SEL_CRED_INVALIDA)
            if erro_cred.count() > 0 and erro_cred.first.is_visible():
                return "credencial"
            if page.locator(_SEL_SESSAO_EXPIRADA).count() > 0:
                return "licenca"
            if page.locator(_SEL_USERNAME).count() == 0:
                ausencias += 1
                if ausencias >= _POLLS_CONFIRMA_SUCESSO:
                    # Entramos — mas a home pode estar AINDA CARREGANDO. Devolver
                    # aqui uma pagina em transito foi o que quebrou os fluxos que
                    # navegam logo depois do login (ver _navegar_para_chamado_pw):
                    # o antigo sleep(3) fixo dava esse tempo por acidente.
                    _aguardar_pagina_assentar(page)
                    return "sucesso"
            else:
                ausencias = 0  # voltou a tela de login: nao entrou
        except Exception:
            # DOM em transicao (navegacao pos-login em curso): reavalia no
            # proximo ciclo em vez de estourar. Nao conta como ausencia.
            ausencias = 0
        time.sleep(intervalo_s)
    return "indefinido"


def _aguardar_pagina_assentar(page, timeout_ms: int = 30000) -> None:
    """Espera a navegacao em curso terminar. NUNCA levanta — e uma precaucao.

    Existe porque `page.evaluate` e `page.locator` operam no documento ATUAL: se
    ha uma navegacao pendente, o documento que chega descarta o que fizemos.
    """
    for estado in ("domcontentloaded", "load"):
        try:
            page.wait_for_load_state(estado, timeout=timeout_ms)
        except Exception:
            pass


def _sessao_expirada_pw(page) -> bool:
    try:
        return page.locator(_SEL_SESSAO_EXPIRADA).count() > 0
    except Exception:
        return False


def _esperar_chamado_carregado(page, timeout_ms: int = 30000) -> bool:
    """True se o chamado abriu (botao de log do evento no DOM).

    `state="attached"` de proposito: o fluxo Selenium usava
    `presence_of_element_located` (presenca no DOM), e o default do Playwright e
    "visible" — deixar o default era uma divergencia silenciosa entre os dois
    motores. Quem clica depois (`#menuActions`) tem espera de actionability
    propria, entao presenca aqui basta.
    """
    try:
        page.wait_for_selector(
            _SEL_CHAMADO_CARREGADO, state="attached", timeout=timeout_ms)
        return True
    except PWTimeout:
        return False


def _navegar_para_chamado_pw(page, numero_chamado: str, log) -> bool:
    id_final = _normalizar_id_assyst(numero_chamado)
    url = _URL_CHAMADO.format(id_final=id_final)
    log(f"Navegando para o chamado: {numero_chamado}", "status")

    # A pagina pode chegar aqui AINDA CARREGANDO — o caso classico e vir direto
    # do login. Trocar o location.href no meio de uma navegacao pendente PERDE a
    # rota: o documento que chega sobrescreve o destino e o Chrome fica parado na
    # home, sem nunca abrir o chamado (era exatamente o sintoma do Iniciar
    # Atendimento: "abriu o navegador mas nao navegou").
    _aguardar_pagina_assentar(page)

    # O Assyst e SPA com rota em hash: trocar window.location.href mantem a
    # aplicacao viva, enquanto um goto() recarregaria tudo do zero.
    page.evaluate("destino => window.location.href = destino", url)
    if _esperar_chamado_carregado(page):
        log("Chamado carregado!", "success")
        return True

    # Nao abriu. O reload cobre a pagina que travou; reaplicar a rota depois dele
    # cobre o caso da rota ter sido engolida (se ela pegou, o hash ja esta na URL
    # atual e o evaluate vira no-op).
    log("Reforcando carregamento...", "info")
    try:
        page.reload()
    except Exception as e:
        log(f"Falha ao recarregar: {e}", "error")
        return False
    _aguardar_pagina_assentar(page)
    page.evaluate("destino => window.location.href = destino", url)
    if _esperar_chamado_carregado(page):
        log("Chamado carregado apos refresh.", "success")
        return True

    log(f"Chamado nao carregou: {numero_chamado}", "error")
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
