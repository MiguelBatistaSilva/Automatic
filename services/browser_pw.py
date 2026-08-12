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

import os
import subprocess
import time
import urllib.request

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# Reaproveita as constantes/regras ja validadas no fluxo Selenium, para as duas
# implementacoes nao divergirem com o tempo.
from services.assyst_common import (
    _URL_HOME, _URL_CHAMADO, _normalizar_id_assyst, _so_o_nome,
)
from services.paths import PERFIL_NAVEGADOR_DIR

_SEL_USERNAME = "input[name='j_username']"
_SEL_PASSWORD = "input[name='j_password']"
_SEL_LOGIN = "#loginSubmit"
_SEL_SESSAO_EXPIRADA = "ol.axios-logout-error"
_SEL_CRED_INVALIDA = "ol.errormsg"
_SEL_CHAMADO_CARREGADO = "#btlogEvent"
_SEL_TITULO_CHAMADO = "h1#contentPaneTitle"
_SEL_IFRAME_EDITOR = "iframe[title*='formattedRemarks']"

# Respiro entre retentativas de login. Existe para nao martelar o Assyst em laco
# apertado quando as licencas estao esgotadas (o fluxo Selenium tinha o mesmo
# 0.5s). Curto de proposito: a aba Licencas ganha a licenca de quem estiver
# tentando primeiro, entao ficar lento aqui custa a licenca.
_PAUSA_ENTRE_TENTATIVAS_S = 0.5

# Quantos polls consecutivos sem o campo de usuario confirmam que entramos.
# Com intervalo_s=0.15 -> ~0.6s de ausencia sustentada.
_POLLS_CONFIRMA_SUCESSO = 4


# Tamanho da tela no modo HEADLESS. Sem janela nao existe "maximizar", e o
# viewport padrao do Playwright (1280x720) e apertado demais para o Assyst: a
# grade Dojo e VIRTUALIZADA (so desenha as linhas visiveis), entao a altura muda
# quantas linhas existem no DOM — e o kb_manager rola a grade contando com isso.
# Full HD faz o headless enxergar a mesma tela que o operador ve maximizado.
_VIEWPORT_HEADLESS = {"width": 1920, "height": 1080}


class NavegadorPW:
    """
    Abre o Chrome ja instalado na maquina (channel="chrome"), sem chromedriver.

    E justamente aqui que mora o ganho da migracao: o Playwright fala CDP direto
    com o navegador, entao nao existe binario de driver para casar de versao
    quando o Chrome atualiza sozinho.

    HEADLESS E O PADRAO. A janela existia para acompanhar o fluxo com medo de ele
    dar errado; esse papel passou para os logs, que dizem em QUAL PASSO parou —
    coisa que olhar a tela nunca disse. Sem janela o fluxo tambem para de disputar
    o foco do teclado com quem esta usando a maquina, e o app fica pronto para
    rodar num servidor.

    Quem NAO usa esta classe: a aba Licencas. La o produto final e a janela
    aberta para o usuario trabalhar, entao ela usa o `NavegadorAvulsoPW`, que
    sempre tem janela.

    Uso:
        with NavegadorPW(log) as page:                  # sem janela (fluxos)
            ...
        with NavegadorPW(log, headless=False) as page:  # com janela (teste_*.py)
            ...
    """

    def __init__(self, log_func, headless: bool = True):
        self.log = log_func
        self.headless = headless
        self._pw = None
        self._browser = None
        self._context = None
        self.page = None

    def __enter__(self):
        modo = "sem janela" if self.headless else "com janela"
        self.log(f"Iniciando Chrome via Playwright ({modo}, sem chromedriver)...",
                 "info")
        self._pw = sync_playwright().start()

        # --start-maximized so faz sentido com janela; sem ela e ruido.
        args = ["--disable-infobars"]
        if not self.headless:
            args.insert(0, "--start-maximized")

        self._browser = self._pw.chromium.launch(
            channel="chrome",
            headless=self.headless,
            args=args,
        )
        # Com janela, `no_viewport` deixa a pagina ocupar a janela real em vez do
        # viewport padrao de 1280x720. Sem janela nao ha o que ocupar, entao o
        # tamanho precisa ser dito (ver _VIEWPORT_HEADLESS).
        self._context = (
            self._browser.new_context(viewport=_VIEWPORT_HEADLESS)
            if self.headless
            else self._browser.new_context(no_viewport=True)
        )
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


# ---------------------------------------------------------------------------
# Chrome AVULSO — o navegador da aba Licencas
# ---------------------------------------------------------------------------
#
# Porta fixa (e nao sorteada) DE PROPOSITO: se o Chrome do perfil dedicado ja
# estiver aberto de uma execucao anterior, a porta ja responde e a gente conecta
# nele em vez de subir um segundo. Assim clicar duas vezes em "Abrir sessao"
# reaproveita a janela — e o `_fazer_login_pw` conclui "Sessao ja ativa" na hora.
_PORTA_CDP = 9333

# Perfil DEDICADO, separado do Chrome do dia a dia. Nao e escolha de estilo: a
# partir do Chrome 136 o `--remote-debugging-port` e IGNORADO quando o
# `--user-data-dir` e o perfil padrao (correcao de seguranca da Google). Sem
# perfil proprio nao ha porta de depuracao, e sem porta nao ha como automatizar
# o login.
#
# E FICA FORA DA PASTA DO PROJETO — este endereco custou caro. Com o perfil em
# `data/`, o Chrome criava ~1500 arquivos DENTRO da arvore que o `reflex run`
# observa para hot-reload (`reload_paths = [Path.cwd()]`). O watcher disparava, o
# backend reiniciava e matava a thread do worker logo depois de "Abrindo o
# Chrome": a janela abria no Assyst e nunca era logada, sem erro nenhum no log.
# Rodando fora do Reflex nao ha watcher, entao o bug NAO reproduzia no terminal.
_PERFIL_AVULSO = PERFIL_NAVEGADOR_DIR

# 60s, nao 30s: numa maquina fria (perfil recem-criado, antivirus varrendo o
# processo novo) o Chrome pode demorar bem mais que 30s para abrir a porta. Com o
# teto curto a gente desistia ANTES de ele terminar de subir — e a janela abria
# logo depois, ja sem ninguem para logar nela. E exatamente o quadro de "o Chrome
# abriu no Assyst mas nao logou".
_TIMEOUT_SUBIR_CHROME_S = 60.0


def _caminho_do_chrome() -> str | None:
    """Onde esta o chrome.exe desta maquina ("" nenhum -> None).

    O registro e a fonte boa (segue instalacao por usuario e por maquina); os
    caminhos fixos sao so a rede de seguranca para quando a chave nao existe.
    """
    import winreg

    chave = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"
    for raiz in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(raiz, chave) as k:
                valor, _ = winreg.QueryValueEx(k, "")
        except OSError:
            continue
        if valor and os.path.exists(valor):
            return valor

    for base in (os.environ.get("PROGRAMFILES"),
                 os.environ.get("PROGRAMFILES(X86)"),
                 os.environ.get("LOCALAPPDATA")):
        if not base:
            continue
        caminho = os.path.join(base, "Google", "Chrome", "Application", "chrome.exe")
        if os.path.exists(caminho):
            return caminho
    return None


def _cdp_respondendo(porta: int, timeout_s: float = 1.0) -> bool:
    """Ja ha um Chrome ouvindo CDP nesta porta?"""
    try:
        with urllib.request.urlopen(
                f"http://127.0.0.1:{porta}/json/version", timeout=timeout_s):
            return True
    except Exception:
        return False


class NavegadorAvulsoPW:
    """Chrome que sobrevive ao fim da automacao E CONTINUA UTILIZAVEL.

    E o navegador da aba Licencas, cujo produto final nao e um dado extraido: e
    a JANELA aberta e logada, para o usuario trabalhar no Assyst.

    POR QUE NAO DA PARA USAR O `NavegadorPW` COM 'manter_aberto':
    o Playwright configura o Chrome para PAUSAR toda aba nova ate o cliente
    liberar (`Target.setAutoAttach` com `waitForDebuggerOnStart`). Enquanto o
    fluxo roda, ele libera. Quando a thread do worker morre, a conexao continua
    de pe mas sem ninguem do outro lado: a aba que ja existia funciona, e toda
    aba NOVA nasce em branco e travada. Era o que os usuarios relatavam. Abrir
    o mesmo Assyst num Chrome normal e abrir 10 abas funcionou — ou seja, o
    limite nao era do Assyst.

    A INVERSAO QUE CONSERTA: quem abre o Chrome somos NOS (subprocess), e o
    Playwright apenas CONECTA nele por CDP. Ao sair, desconectamos; as sessoes
    CDP morrem e com elas a regra de pausar abas. O Chrome fica um Chrome
    comum — e nao morre nem quando o app fecha, porque nao e o Playwright que o
    controla. E o equivalente exato do `detach=True` do Selenium, que era o que
    funcionava antes da migracao.

    Uso:
        with NavegadorAvulsoPW(log) as page:
            _fazer_login_pw(page, matricula, senha, log)
        # a janela continua aberta e usavel
    """

    def __init__(self, log_func, porta: int = _PORTA_CDP, perfil=_PERFIL_AVULSO):
        self.log = log_func
        self.porta = porta
        self.perfil = perfil
        self._pw = None
        self._browser = None
        self.page = None

    def _subir_chrome(self) -> None:
        exe = _caminho_do_chrome()
        if exe is None:
            raise RuntimeError(
                "O Google Chrome nao foi encontrado neste computador. Instale-o "
                "para usar a aba Licencas.")

        self.perfil.mkdir(parents=True, exist_ok=True)
        self.log("Abrindo o navegador...", "status")
        processo = subprocess.Popen(
            [exe,
             f"--remote-debugging-port={self.porta}",
             f"--user-data-dir={self.perfil}",
             "--no-first-run",
             "--no-default-browser-check",
             "--start-maximized",
             # O Assyst vai na PROPRIA linha de comando: assim a aba que o
             # usuario ve na frente ja nasce sendo a do Assyst. Deixar o Chrome
             # abrir na Nova Aba e navegar depois pelo Playwright era o que fazia
             # parecer "uma aba comum" — a Nova Aba e uma pagina `chrome://`, que
             # o Playwright nao controla e as vezes nem lista, entao ele criava
             # OUTRA aba, atras, e carregava o Assyst nela.
             _URL_HOME],
            # DETACHED_PROCESS: o Chrome nasce fora do console e do grupo de
            # processos do app. Sem isso ele herdaria o console do Python e
            # poderia ser derrubado junto com ele.
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )

        # O CAMINHO FELIZ E MUDO daqui ate o login. O usuario da aba Licencas quer
        # saber se pode comecar a trabalhar; porta, PID e tempo de resposta sao
        # assunto de quem mantem o codigo. O detalhe tecnico so aparece quando
        # algo DA ERRADO — que e quando ele deixa de ser ruido e vira pista.
        inicio = time.monotonic()
        fim = inicio + _TIMEOUT_SUBIR_CHROME_S
        proximo_aviso = inicio + 8.0
        while time.monotonic() < fim:
            if _cdp_respondendo(self.porta):
                return

            # O Chrome MORREU em vez de subir? Acontece quando ele decide
            # delegar para uma instancia ja existente do mesmo perfil: o
            # processo novo sai na hora e a porta nunca abre. Esperar o timeout
            # inteiro nesse caso e so demora.
            if processo.poll() is not None:
                raise RuntimeError(
                    "O navegador fechou sozinho ao abrir. Normalmente e uma "
                    "janela do navegador do Automatic que ficou aberta: feche "
                    "todas e clique em Abrir sessao de novo.")

            # Passar de 8s sem resposta e incomum. Avisar evita a sensacao de
            # travamento numa espera que pode chegar a um minuto.
            agora = time.monotonic()
            if agora >= proximo_aviso:
                self.log("O navegador esta demorando mais que o normal para "
                         "abrir; aguarde...", "info")
                proximo_aviso = agora + 8.0
            time.sleep(0.3)

        raise RuntimeError(
            "O navegador abriu mas nao respondeu a tempo. Feche as janelas do "
            "navegador do Automatic e tente de novo; se persistir, reinicie o "
            f"computador. (detalhe tecnico: sem resposta na porta {self.porta} "
            f"em {_TIMEOUT_SUBIR_CHROME_S:.0f}s, PID {processo.pid})")

    def __enter__(self):
        if _cdp_respondendo(self.porta):
            self.log("Usando a janela do navegador que ja esta aberta.", "info")
        else:
            self._subir_chrome()

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.connect_over_cdp(
            f"http://127.0.0.1:{self.porta}")

        contexto = (self._browser.contexts[0] if self._browser.contexts
                    else self._browser.new_context())
        self.page = self._escolher_aba(contexto)

        # Traz a aba escolhida para a frente. Sem isto o Assyst pode carregar
        # numa aba de FUNDO enquanto o usuario continua olhando outra — o
        # sintoma de "abriu uma aba comum e nao foi para o Assyst".
        try:
            self.page.bring_to_front()
        except Exception:
            pass  # perda cosmetica; nao vale derrubar a sessao por isso

        # ENTREGAR A PAGINA ASSENTADA, nunca em transito. A aba e capturada
        # assim que EXISTE, com a navegacao inicial (o Assyst da linha de
        # comando) ainda em curso. Quem recebe a page dispara um `goto` por cima
        # dela: duas navegacoes competindo, e os 7s que o `_fazer_login_pw`
        # espera pelo campo de usuario comecam a contar numa tela que ainda esta
        # montando. Estourando esses 7s, ele conclui "Sessao ja ativa" e devolve
        # sucesso SEM TER DIGITADO NADA — Chrome aberto no Assyst, sem login.
        # Mesma licao ja aplicada em _navegar_para_chamado_pw.
        _aguardar_pagina_assentar(self.page)
        return self.page

    def _escolher_aba(self, contexto, timeout_s: float = 15.0):
        """A aba onde o login vai acontecer — a do Assyst, se ela existir.

        NAO da para simplesmente pegar `pages[0]`. O Playwright so enxerga
        paginas que ele consegue controlar: a Nova Aba do Chrome e uma URL
        `chrome://`, que fica de fora. Numa sessao recem-aberta a lista podia vir
        VAZIA, e o `new_page()` do codigo anterior criava uma aba ATRAS da que o
        usuario estava vendo — dai a impressao de que "abriu uma aba comum e nao
        foi para o Assyst".

        Agora o Chrome ja sobe apontado para o Assyst (ver `_subir_chrome`), e
        aqui a gente ESPERA essa aba aparecer: a porta CDP passa a responder
        assim que o processo do Chrome sobe, o que e ANTES de a primeira aba
        existir. Ler a lista uma vez so cairia justo nesse buraco.

        Esgotado o tempo, abre uma aba NOVA em vez de aproveitar outra qualquer.
        Isso e o caso de REAPROVEITAR um Chrome ja aberto em que o usuario fechou
        a aba do Assyst: aproveitar a aba dele significaria navegar por cima do
        que ele estava fazendo. Uma aba a mais e barata; perder o trabalho alheio
        nao e.
        """
        base = _URL_HOME.split("//", 1)[-1].split("/", 1)[0]  # host do Assyst

        fim = time.monotonic() + timeout_s
        paginas: list = []
        while time.monotonic() < fim:
            paginas = list(contexto.pages)
            for pagina in paginas:
                if base in pagina.url:
                    return pagina
            time.sleep(0.3)

        # Fora do caminho feliz: aqui o detalhe tecnico deixa de ser ruido e vira
        # a unica pista de por que a aba certa nao apareceu.
        self.log("Nao achei a aba do Assyst; abrindo uma nova. (abas vistas: "
                 f"{[p.url for p in paginas] or 'nenhuma'})", "info")
        return contexto.new_page()

    def __exit__(self, exc_type, exc, tb):
        # SO `stop()`. Nada de `browser.close()`: com `connect_over_cdp` ele
        # limparia os contextos e fecharia as abas do usuario — justo o que
        # queremos preservar. O `stop()` derruba o processo do driver, e o
        # Chrome sobrevive porque nao foi o Playwright que o abriu.
        try:
            if self._pw is not None:
                self._pw.stop()
        except Exception as e:
            # Nao e cosmetico: se a desconexao falhar, o navegador pode ficar
            # com as abas travadas — que e exatamente o problema que esta classe
            # existe para resolver. Por isso a instrucao pratica vem junto.
            self.log("Nao consegui soltar o navegador por completo. Se as abas "
                     "novas travarem, feche o navegador e abra a sessao de novo. "
                     f"(detalhe tecnico: {e})", "error")
        self._pw = self._browser = self.page = None
        self.log("Sessao aberta. Pode usar o navegador normalmente.", "success")
        return False


# Teto de falhas TECNICAS seguidas (goto/fill/click que nem chegaram a produzir
# uma tela). Nao limita a espera por licenca: aquela e uma tela que CARREGOU e
# trouxe o banner, e zera este contador. Existe porque "insistir para sempre" so
# faz sentido enquanto ha um Assyst do outro lado respondendo — sem teto, um
# defeito qualquer prende a thread do worker e o botao da aba nunca reabilita.
_MAX_FALHAS_TECNICAS = 10


def _navegador_morreu(page) -> bool:
    """A aba/o navegador sumiu? Entao nao ha o que retentar.

    E a diferenca entre "o Assyst engasgou" (insista) e "o usuario fechou o
    Chrome" (desista). Sem esta distincao, fechar a janela deixava o laco
    girando para sempre: o `goto` levantava 'Target closed', o `except Exception`
    engolia, e a thread nunca terminava — o botao 'Abrir sessao' ficava
    desabilitado ate reiniciar o app.
    """
    try:
        return page.is_closed()
    except Exception:
        return True  # nem da para perguntar: trate como morto


def _credenciais_na_tela(page) -> bool:
    """Os dois campos de login estao mesmo preenchidos AGORA?

    Existe porque a tela de login do Assyst se redesenha sozinha (e o que ela faz
    ao recusar por licencas). Se ela redesenhar ENTRE os dois `fill`, o usuario
    volta a ficar vazio e o clique envia o formulario pela metade — e o Assyst
    responde "credencial invalida", que e o UNICO desfecho que aborta o laco.
    Ou seja: um redesenho passageiro derrubaria a sessao de vez, culpando uma
    senha que estava certa.
    """
    try:
        return bool(page.input_value(_SEL_USERNAME, timeout=2000).strip()
                    and page.input_value(_SEL_PASSWORD, timeout=2000))
    except Exception:
        return False


def _fazer_login_pw(page, usuario: str, senha: str, log) -> bool:
    """Insiste no login ate entrar. Só desiste se a CREDENCIAL estiver errada.

    O laco e infinito de proposito (aba Licencas): quando todas as licencas do
    Assyst estao em uso, a unica saida e retentar ate alguem sair. Por isso
    NENHUMA falha tecnica pode escapar daqui — uma excecao no `goto`/`fill`
    subindo pela pilha mata a thread do worker e o app aparenta ter um "limite
    de tentativas" (era o que acontecia: o Assyst engasga justamente quando esta
    saturado, que e exatamente quando este laco precisa insistir).

    POR QUE OS `except` SAO LARGOS: eles capturavam so `PWTimeout`, e isso NAO
    cobre o que de fato acontece aqui. O Playwright levanta PWTimeout apenas na
    espera estourada; elemento que se desprende no meio do `fill` (a tela de
    login redesenhando), contexto de execucao destruido por navegacao e erro de
    rede no `goto` sao `playwright.sync_api.Error`. Todos furavam o laco. E a
    mesma licao ja anotada no flow_desmembramento_pw, que aqui tinha ficado de
    fora.

    ...MAS O LACO PRECISA DE SAIDA. Alargar os `except` sem isso trocou um
    defeito por outro: fechar a janela do Chrome passou a ser "falha retentavel",
    o laco girava para sempre e a thread do worker nunca terminava — na aba
    Licencas o botao 'Abrir sessao' ficava desabilitado ate reiniciar o app. Por
    isso existem duas saidas de emergencia:
      - `_navegador_morreu` -> a aba/janela sumiu, nao ha o que retentar;
      - `_MAX_FALHAS_TECNICAS` -> falhas seguidas que nem produziram tela.
    Nenhuma das duas limita a espera por LICENCA, que e o caso que precisa
    insistir indefinidamente: ali a tela carrega, o banner aparece, e o contador
    de falhas tecnicas zera.

    As credenciais NAO precisam ser apagadas entre as tentativas: cada volta do
    laco recomeca com `page.goto(_URL_HOME)`, que traz um documento novo, e o
    `fill()` do Playwright substitui o valor inteiro do campo (nao acumula).
    """
    tentativa = 0
    falhas_tecnicas = 0

    def desistir(motivo: str) -> bool:
        log(motivo, "error")
        return False

    while True:
        if _navegador_morreu(page):
            return desistir("A janela do navegador foi fechada; login cancelado.")
        if falhas_tecnicas >= _MAX_FALHAS_TECNICAS:
            return desistir(
                f"{falhas_tecnicas} falhas seguidas sem conseguir carregar a tela "
                "de login. Verifique a conexao com o CATI e tente de novo.")

        try:
            page.goto(_URL_HOME)
        except Exception as e:
            falhas_tecnicas += 1
            log(f"A home nao respondeu ({e}); tentando novamente...", "error")
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
        except Exception as e:
            # AQUI O `except` LARGO NAO PODE SER JUNTO COM O DE CIMA. "Estourou o
            # tempo" significa "nao ha tela de login" (entramos); qualquer OUTRO
            # erro significa so que a espera foi atrapalhada pelo DOM em
            # transicao. Tratar os dois igual devolveria "logado" numa tela de
            # login — o mesmo falso sucesso que o `_POLLS_CONFIRMA_SUCESSO` ja
            # existe para impedir mais adiante.
            falhas_tecnicas += 1
            log(f"A home nao se estabilizou ({e}); tentando novamente...", "info")
            time.sleep(_PAUSA_ENTRE_TENTATIVAS_S)
            continue

        # A tela de login CARREGOU: o que veio antes nao era um problema
        # persistente. Zerar aqui e o que mantem o teto de falhas tecnicas longe
        # da espera por licenca — que passa por este ponto a cada rodada.
        falhas_tecnicas = 0

        tentativa += 1
        log(f"Realizando login (tentativa {tentativa})...", "status")
        try:
            page.fill(_SEL_USERNAME, usuario)
            page.fill(_SEL_PASSWORD, senha)
        except Exception as e:
            falhas_tecnicas += 1
            log(f"Tela de login travou ao preencher ({e}); tentando novamente... "
                f"(tentativa {tentativa})", "error")
            time.sleep(_PAUSA_ENTRE_TENTATIVAS_S)
            continue

        # Confere ANTES de clicar (ver `_credenciais_na_tela`): enviar o
        # formulario pela metade e o unico jeito de este laco desistir por
        # engano.
        if not _credenciais_na_tela(page):
            falhas_tecnicas += 1
            log(f"A tela de login se redesenhou no meio do preenchimento; "
                f"refazendo... (tentativa {tentativa})", "info")
            time.sleep(_PAUSA_ENTRE_TENTATIVAS_S)
            continue

        try:
            page.click(_SEL_LOGIN)
        except Exception as e:
            falhas_tecnicas += 1
            log(f"Nao consegui clicar em entrar ({e}); tentando novamente... "
                f"(tentativa {tentativa})", "error")
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
            # Conta como falha tecnica: um Assyst que nunca se decide nao e
            # contencao de licenca, e sem teto prenderia a thread para sempre.
            falhas_tecnicas += 1
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


def _digitos(texto: str) -> str:
    """So os digitos — usado para comparar numeros de chamado sem depender do
    prefixo (o usuario digita 'S2123456', 'r2123456' ou so '123456')."""
    return "".join(c for c in texto if c.isdigit())


def _numero_do_titulo(page) -> str:
    """Numero do chamado ABERTO agora, lido do titulo do painel ("" se indisponivel)."""
    try:
        texto = page.locator(_SEL_TITULO_CHAMADO).inner_text().strip()
    except Exception:
        return ""  # painel ainda nao montado / DOM em transicao
    return texto.split()[0].upper() if texto else ""


def _usuario_afetado_pw(page) -> str:
    """Nome do 'Usuário afetado' do chamado ABERTO agora ("" se indisponivel).

    MIRA PELO `name`, NAO PELO ID. O id do campo carrega o prefixo do formulario
    (`ManageEventForm_EC61_affectedUser_textNode`), e o prefixo muda por tela —
    `ES3` na criacao de Requisição, `EC61` num chamado salvo. O `name` e sempre
    `affectedUser.text`, entao nao ha prefixo para descobrir.

    O `:visible` NAO e detalhe. O Assyst e SPA e a tela do chamado ANTERIOR
    continua no DOM enquanto a nova monta — e ela TAMBEM e um `ManageEventForm_`
    com o seu proprio `affectedUser.text`. Sem o filtro, percorrer uma lista de
    chamados leria o usuario do chamado de tras, calado. E a mesma corrida ja
    corrigida em `_esperar_chamado_carregado` e na captura do numero do filho; o
    formulario velho fica escondido, entao a visibilidade separa os dois.

    Devolve "" em qualquer problema: isto e enfeite de tabela, nunca pode
    derrubar a analise de um chamado.
    """
    try:
        campo = page.locator("input[name='affectedUser.text']:visible")
        if campo.count() == 0:
            return ""
        return _so_o_nome(campo.first.input_value())
    except Exception:
        return ""


def _esperar_chamado_carregado(page, numero_chamado: str | None = None,
                               timeout_ms: int = 30000, log=None) -> bool:
    """True quando a tela do chamado PEDIDO esta aberta.

    CORRIDA QUE ESTA FUNCAO EXISTE PARA MATAR: o Assyst e uma SPA e a tela do
    chamado ANTERIOR continua no DOM enquanto a nova e montada. Esperar so a
    PRESENCA de `#btlogEvent` (o criterio antigo) retornava True NA HORA em
    qualquer navegacao feita a partir de um chamado ja aberto: o fluxo logava
    "Chamado carregado!" instantaneamente e ia clicar no menu da tela VELHA. E o
    mesmo erro de "presenca em vez de mudanca" ja corrigido na captura do numero
    do filho.

    Por isso o criterio agora e o TITULO do painel bater com o chamado pedido.
    Comparamos so os digitos: o titulo traz 'S2123456' e o usuario pode ter
    digitado o numero sem prefixo.

    Sem `numero_chamado` cai no criterio antigo (so presenca).
    """
    if not numero_chamado:
        try:
            page.wait_for_selector(
                _SEL_CHAMADO_CARREGADO, state="attached", timeout=timeout_ms)
            return True
        except PWTimeout:
            return False

    esperado = _digitos(numero_chamado)
    fim = time.monotonic() + timeout_ms / 1000
    visto = ""
    while time.monotonic() < fim:
        try:
            # `count()` em vez de wait_for_selector: aqui quem manda no tempo e o
            # laco, e o botao do evento e so metade do criterio.
            if page.locator(_SEL_CHAMADO_CARREGADO).count() > 0:
                visto = _numero_do_titulo(page)
                if visto and _digitos(visto) == esperado:
                    return True
        except Exception:
            pass  # DOM em transicao: reavalia no proximo ciclo
        time.sleep(0.2)

    # Diagnostico que faltava: dizer QUAL chamado ficou na tela evita horas
    # procurando erro de seletor quando o problema foi a navegacao.
    if log and visto:
        log(f"A tela aberta e do chamado {visto}, nao do {numero_chamado}.", "error")
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
    if _esperar_chamado_carregado(page, numero_chamado):
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
    if _esperar_chamado_carregado(page, numero_chamado, log=log):
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


def _capturar_numero_filho_pw(page, log, titulo_antes: str,
                              timeout_s: float = 15.0) -> str:
    """Captura o numero do chamado filho gerado pelo Assyst apos salvar.

    Recebe `titulo_antes` -- o titulo do painel (via `_numero_do_titulo`) lido
    pelo CHAMADOR imediatamente ANTES do clique em Salvar, quando a tela ja
    diz "Insira os detalhes do <servico>". So aceita um titulo que MUDOU em
    relacao a esse valor E que tem algum digito; sem os dois, continua
    esperando ate o teto e devolve "".

    ISSO NAO REPETE O BUG DO SELENIUM (13/07/2026, revertido por ter ficado
    lento): la a referencia era tomada ANTES de 'Salvar como Novo', e o titulo
    passava por varios estados intermediarios ate estabilizar -- esperar
    'mudou' a partir dali demorava e nao capturava. Aqui a referencia e tomada
    ANTES do Salvar final, quando o titulo ja esta parado em "Insira os
    detalhes...": so falta UMA transicao, para o numero do filho. E o mesmo
    ponto de referencia que ja funciona no `_capturar_numero` da Requisicao.

    NAO TRAVA: o teto e sempre respeitado, poll curto (200ms), e qualquer
    erro de leitura de tela (`_numero_do_titulo` devolve "" em transicao de
    DOM) so faz o laco tentar de novo no proximo ciclo, nunca bloqueia.

    Antes disto, um `wait_for_timeout(2000)` cego + leitura unica podia
    devolver o titulo AINDA em transicao ("Insira os detalhes...") como se
    fosse o numero do filho -- ele passava no `if num_filho:` do chamador e
    virava um numero de chamado inventado no checkpoint e no TXT de filhos.
    """
    fim = time.monotonic() + timeout_s
    while time.monotonic() < fim:
        atual = _numero_do_titulo(page)
        if atual and atual != titulo_antes and any(c.isdigit() for c in atual):
            log(f"Numero do chamado filho capturado: {atual}", "info")
            return atual
        page.wait_for_timeout(200)
    log("Nao foi possivel capturar o numero do filho (titulo nao mudou a "
        f"tempo, {timeout_s:.0f}s). O chamado pode ter sido salvo mesmo assim "
        "-- confira a tela.", "error")
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
