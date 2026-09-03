"""
senior/service.py — Automação de ponto na Senior HCM.

Site e credencial totalmente à parte do Assyst (ver senior/credenciais.py).
Adaptado do script solo `bater_ponto.py` (trazido de C:\\senior): mesma lógica de
login/clique, agora sem CLI — fala com o state por `log(msg, tipo)`, no mesmo
contrato que os outros fluxos (ver state/flow_runner.py).

Usa o Edge já instalado (channel="msedge") com PERFIL PERSISTENTE — diferente do
NavegadorPW do Assyst (perfil novo a cada execução): aqui o login/captcha só
precisa ser resolvido uma vez, e as próximas batidas entram direto.
"""
import time
from datetime import datetime, timedelta

from playwright.sync_api import sync_playwright

from services.paths import PERFIL_PONTO_DIR

URL = ("https://platform.senior.com.br/senior-x/#/Gest%C3%A3o%20de%20Pessoas%20"
       "%7C%20HCM/1/res:%2F%2Fsenior.com.br%2Fhcm%2Fpontomobile%2FclockingEvent"
       "?category=frame&link=https:%2F%2Fplatform.senior.com.br%2Fhcm-pontomobile"
       "%2Fhcm%2Fpontomobile%2F%23%2Fclocking-event&withCredentials=true&r=0")

SELETOR_USUARIO = "#username-input-field"
SELETOR_BOTAO_PROXIMO = "#nextBtn"
SELETOR_SENHA = "#password-input-field"
SELETOR_BOTAO_LOGIN = "#loginbtn"
SELETOR_LEMBRAR = "#rememberme-input-checkbox"
SELETOR_LEMBRAR_LABEL = "#div-rememberme label"
SELETOR_BOTAO_PONTO = "button:has-text('Registrar Ponto')"

TIMEOUT_SEGUNDOS = 60
TOLERANCIA_MINUTOS = 1
TENTATIVAS_PONTO = 3
ESPERA_ENTRE_TENTATIVAS_SEGUNDOS = 15


def validar_horario(texto: str):
    """Converte 'HH:MM' em datetime de HOJE. None se inválido."""
    try:
        t = datetime.strptime(texto.strip(), "%H:%M").time()
    except ValueError:
        return None
    hoje = datetime.now()
    return hoje.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)


def _fazer_login_se_preciso(pagina, usuario, senha, log):
    log("Verificando estado da sessao...", "info")
    pagina.wait_for_timeout(2000)

    if not pagina.locator(SELETOR_USUARIO).is_visible():
        log("Sessao salva: usuario ja autenticado pelo perfil.", "info")
        return

    log("Tela de login detectada. Preenchendo dados...", "info")

    try:
        valor_atual = pagina.locator(SELETOR_USUARIO).input_value()
        if not valor_atual:
            pagina.fill(SELETOR_USUARIO, usuario)
        if pagina.locator(SELETOR_BOTAO_PROXIMO).is_visible():
            pagina.click(SELETOR_BOTAO_PROXIMO)
    except Exception:
        log("Nao foi possivel interagir com campo Usuario/Proximo, tentando seguir.", "info")

    try:
        pagina.wait_for_selector(SELETOR_SENHA, timeout=5000, state="visible")
        pagina.fill(SELETOR_SENHA, senha)

        try:
            if pagina.locator(SELETOR_LEMBRAR).is_visible():
                pagina.check(SELETOR_LEMBRAR, force=True, timeout=2000)
            else:
                pagina.click(SELETOR_LEMBRAR_LABEL, timeout=2000)
        except Exception:
            pass

        pagina.click(SELETOR_BOTAO_LOGIN)
        pagina.wait_for_selector(SELETOR_SENHA, state="hidden", timeout=15000)
        log("Login efetuado com sucesso.", "info")
    except Exception:
        log("Campo de senha nao solicitado ou ja processado.", "info")

    if pagina.locator("#recaptcha:not(.hidden)").count() > 0:
        log("CAPTCHA detectado! Resolva-o na janela do navegador...", "status")
        pagina.wait_for_selector(SELETOR_SENHA, state="hidden", timeout=120000)


def _achar_frame_do_ponto(pagina):
    limite = time.time() + TIMEOUT_SEGUNDOS
    while time.time() < limite:
        for frame in pagina.frames:
            try:
                if frame.locator(SELETOR_BOTAO_PONTO).count() > 0:
                    return frame
            except Exception:
                continue
        pagina.wait_for_timeout(1000)
    return None


def bater_ponto(pagina, usuario, senha, log, clicar=True) -> bool:
    """Navega, garante login e (se clicar) registra o ponto.
    clicar=False -> simulacao: encontra o botao mas nao clica."""
    log("Iniciando batida de ponto...", "status")

    pagina.goto(URL, wait_until="load")
    _fazer_login_se_preciso(pagina, usuario, senha, log)

    log("Procurando o botao 'Registrar Ponto'...", "info")
    frame = _achar_frame_do_ponto(pagina)
    if frame is None:
        log("ERRO: botao de ponto nao encontrado a tempo.", "error")
        return False

    if not clicar:
        log("SIMULACAO OK: botao 'Registrar Ponto' encontrado. NADA foi registrado.", "status")
        pagina.wait_for_timeout(5000)
        return True

    log("Clicando no botao 'Registrar Ponto'...", "info")
    botao = frame.locator(SELETOR_BOTAO_PONTO).first
    botao.click()

    log("Aguardando confirmacao do sistema...", "info")
    try:
        botao.wait_for_element_state("hidden", timeout=10000)
    except Exception:
        log("O botao nao sumiu imediatamente, aguardando resposta visual...", "info")
    pagina.wait_for_timeout(8000)

    log("Ponto batido com sucesso!", "status")
    return True


def abrir_navegador(p, headless: bool):
    """Abre o Edge com perfil persistente (login salvo entre execucoes)."""
    PERFIL_PONTO_DIR.mkdir(parents=True, exist_ok=True)
    contexto = p.chromium.launch_persistent_context(
        user_data_dir=str(PERFIL_PONTO_DIR),
        channel="msedge",
        headless=headless,
        args=["--start-maximized"] if not headless else [],
        no_viewport=not headless,
        permissions=["geolocation"],
    )
    contexto.set_default_timeout(TIMEOUT_SEGUNDOS * 1000)
    pagina = contexto.pages[0] if contexto.pages else contexto.new_page()
    return contexto, pagina


def testar(usuario: str, senha: str, log, clicar: bool, headless: bool = False) -> bool:
    """Bate (ou simula) o ponto agora, tentando novamente em caso de falha
    (ate TENTATIVAS_PONTO vezes, sem fechar o navegador entre elas — login/captcha
    ja resolvidos continuam valendo)."""
    with sync_playwright() as p:
        contexto, pagina = abrir_navegador(p, headless)
        try:
            for tentativa in range(1, TENTATIVAS_PONTO + 1):
                try:
                    if bater_ponto(pagina, usuario, senha, log, clicar=clicar):
                        return True
                except Exception as e:
                    log(f"Erro na tentativa {tentativa}: {e}", "error")

                if tentativa < TENTATIVAS_PONTO:
                    log(
                        f"Tentativa {tentativa} de {TENTATIVAS_PONTO} falhou. "
                        f"Tentando novamente em {ESPERA_ENTRE_TENTATIVAS_SEGUNDOS}s...",
                        "error",
                    )
                    pagina.wait_for_timeout(ESPERA_ENTRE_TENTATIVAS_SEGUNDOS * 1000)

            log(f"Falha ao bater o ponto apos {TENTATIVAS_PONTO} tentativas.", "error")
            return False
        finally:
            contexto.close()


def rodar_agenda(usuario: str, senha: str, horarios: list[datetime], log,
                  headless: bool = False, deve_parar=None) -> None:
    """Espera cada horario da lista chegar e bate o ponto. Bloqueia a thread
    ate processar todos (ou ate `deve_parar()` virar True)."""
    pendentes = sorted(horarios)
    tolerancia = timedelta(minutes=TOLERANCIA_MINUTOS)

    while pendentes:
        if deve_parar is not None and deve_parar():
            log("Agenda interrompida.", "status")
            return

        agora = datetime.now()
        proximo = pendentes[0]

        if agora >= proximo:
            if agora <= proximo + tolerancia:
                with sync_playwright() as p:
                    contexto, pagina = abrir_navegador(p, headless)
                    try:
                        bater_ponto(pagina, usuario, senha, log)
                    finally:
                        contexto.close()
            else:
                log(f"Horario {proximo.strftime('%H:%M')} ja passou. Pulando.", "error")
            pendentes.pop(0)
        else:
            falta = proximo - agora
            minutos = int(falta.total_seconds() // 60)
            log(f"Proximo ponto as {proximo.strftime('%H:%M')} (em ~{minutos} min)", "info")
            time.sleep(20)

    log("Todos os horarios foram processados.", "status")
