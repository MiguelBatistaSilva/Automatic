"""
services/flow_desmembramento_pw.py — Os tres modos do Desmembramento em Playwright.

Substitui os antigos flow_base / flow_3n / flow_bc (Selenium), que duplicavam
entre si o bloco de criacao do chamado e a fase de Base de Conhecimento. Aqui a
duplicacao some: a classe base `FluxoDesmembramentoPW` concentra as acoes de
navegador, e cada modo e uma subclasse com seu proprio `executar()`.

Papel que era do DriverManager agora e do `NavegadorPW` (services/browser_pw.py):
a page ja chega pronta; o login e feito uma unica vez no inicio de cada execucao.

Medidas de seguranca preservadas do Selenium: checkpoint por chamado (3 estados),
relogin automatico ao expirar a sessao, acumulo de filhos em TXT, e acoes que
reportam fracasso de verdade (nada de "sucesso" por engano).
"""

from playwright.sync_api import TimeoutError as PWTimeout

from services.browser_pw import (
    _fazer_login_pw, _navegar_para_chamado_pw, _sessao_expirada_pw,
    _relogin_pw, _preencher_descricao_pw, _capturar_numero_filho_pw,
)
from services.assyst_common import (
    _montar_descricao, _registrar_filho, _abrir_txt_filhos,
)
from services.kb_manager_pw import BaseAplicadaSemRetorno
from services.checkpoint import (
    inicializar, marcar_salvo, marcar_concluido_linha,
    existe_pendente, foi_concluido, status_linha, numero_filho,
    esta_corrompido,
    STATUS_PENDENTE, STATUS_SALVO, STATUS_CONCLUIDO,
)

# Mensagem unica do guarda de checkpoint ilegivel (os tres modos usam a mesma).
_MSG_CHECKPOINT_ILEGIVEL = (
    "Checkpoint de {chave} existe mas esta ilegivel. ABORTANDO: seguir daqui "
    "faria o fluxo tratar isto como execucao nova e RECRIAR chamados que ja "
    "existem. Confira o arquivo em data/checkpoints/ antes de rodar de novo."
)

# Seletores da tela de edicao do evento (mesmos ids do fluxo Selenium).
_SEL_DUPLICAR = "#btlogAsNewEvent"
_SEL_SALVAR = "#btlogEvent"
# `normalize-space()` em vez de `text()=`: o xpath antigo exigia o texto EXATO, sem
# espaco em volta e num unico no de texto. Um `&nbsp;` ou uma quebra de linha no HTML
# do dialogo ja fazia o seletor achar ZERO elementos.
_SEL_CONTINUAR = (
    "xpath=//span[normalize-space(.)='Continuar']"
    "/ancestor-or-self::span[contains(@role, 'button')]"
)


def _chave_checkpoint(filhos: list[str]) -> str:
    """Gera a chave do checkpoint BC a partir do primeiro filho da lista.

    Mantido aqui (antes vivia no flow_bc.py) porque a aba de Execucao tambem
    importa esta funcao para consultar o checkpoint antes de iniciar.
    """
    return f"bc_{filhos[0].strip()}"


class FluxoDesmembramentoPW:
    """Base comum dos tres modos. Guarda a sessao e concentra as acoes."""

    def __init__(self, page, usuario: str, senha: str, log):
        self.page = page
        self.usuario = usuario
        self.senha = senha
        self.log = log
        # Erguido pelo `_adicionar_bc` quando a base foi aplicada mas a tela nao
        # voltou ao evento: quem depende da tela aberta (a cadeia de duplicacao
        # do modo Criar+Base) reabre o chamado pelo numero.
        self.navegacao_perdida = False

    # ------------------------------------------------------------------
    # Acoes reutilizaveis
    # ------------------------------------------------------------------

    def _relogar_se_preciso(self, numero_chamado: str | None = None) -> bool:
        """Reloga se a sessao expirou. Retorna True se a sessao esta utilizavel.

        Com `numero_chamado` -> reloga E volta para o chamado (para os fluxos
        que duplicam a partir de um evento aberto). Sem numero -> apenas reloga
        (fluxo BC, que navega para o proximo filho logo em seguida).
        """
        if not _sessao_expirada_pw(self.page):
            return True
        if numero_chamado:
            return _relogin_pw(self.page, numero_chamado, self.usuario, self.senha, self.log)
        self.log("Sessao expirada! Reconectando...", "error")
        return _fazer_login_pw(self.page, self.usuario, self.senha, self.log)

    def _clicar_continuar(self) -> bool:
        """Clica no 'Continuar' do dialogo que abre depois de 'Salvar como novo'.

        O CRITERIO DE SUCESSO E O BOTAO SUMIR, nao o clique nao estourar. Essa era
        a falha do codigo anterior: ele so usava `dispatch_event`, que NAO levanta
        excecao quando o widget ignora o evento — entao um clique inocuo passava
        como "Clicado em 'Continuar'." e o fluxo seguia para uma tela que nunca
        mudou. (Foi assim que o dispatch se comportou na sonda do menu da Categoria
        no fluxo de Requisição: "clicou" e nada aconteceu.)

        Por isso: clique NATIVO primeiro (e o que um humano faz), `dispatch` como
        segunda tentativa — o caminho equivalente ao `execute_script('click')` que
        o fluxo Selenium usava e que estava provado — e, entre um e outro, a
        confirmacao de que o dialogo fechou.
        """
        try:
            # `.first`: se a tela tiver mais de um 'Continuar' (dialogo + template
            # escondido), o locator STRICT do Playwright levantaria em vez de pegar
            # o primeiro — que era o comportamento do Selenium.
            botao = self.page.locator(_SEL_CONTINUAR).first
            botao.wait_for(state="visible", timeout=15000)
        except Exception as e:
            self.log(f"O dialogo de 'Continuar' nao apareceu: {e}", "error")
            self._diagnostico_botoes()
            return False

        for modo in ("nativo", "dispatch"):
            try:
                if modo == "nativo":
                    botao.click(timeout=5000)
                else:
                    botao.dispatch_event("click")
            except Exception:
                continue  # este modo nem chegou a clicar; tenta o proximo
            try:
                # Sumiu = o dialogo fechou = o clique valeu. `hidden` cobre tambem
                # o elemento removido do DOM.
                botao.wait_for(state="hidden", timeout=8000)
                self.log(f"Clicado em 'Continuar' ({modo}).", "success")
                return True
            except Exception:
                self.log(f"Clique {modo} em 'Continuar' nao surtiu efeito.", "info")

        self.log("Nao consegui acionar o 'Continuar' — o dialogo continua aberto.",
                 "error")
        self._diagnostico_botoes()
        return False

    def _diagnostico_botoes(self) -> None:
        """Despeja os botoes visiveis. So roda quando algo ja falhou.

        Sem isto, "nao achei o Continuar" nao diz se o dialogo nao abriu, se o
        rotulo mudou ou se ele esta ali com outro texto — e cada hipotese dessas
        custa uma execucao inteira para testar.
        """
        js = r"""
        () => Array.from(document.querySelectorAll("span[role='button'], button"))
            .filter(el => { const r = el.getBoundingClientRect();
                            return r.width > 0 && r.height > 0; })
            .map(el => ((el.id ? el.id + ' | ' : '') +
                        (el.textContent || '').replace(/\s+/g, ' ').trim()).slice(0, 70))
            .filter(t => t);
        """
        try:
            botoes = self.page.evaluate(js) or []
        except Exception as e:
            self.log(f"[DIAG] nao consegui listar os botoes: {e}", "error")
            return
        self.log(f"[DIAG] botoes visiveis agora ({len(botoes)}): "
                 f"{' / '.join(botoes[:25])}", "info")

    def _criar_chamado_filho(self, numero_chamado: str, descricao: str) -> str | None:
        """Duplicar -> Continuar -> Descricao -> Salvar -> capturar filho.

        Retorna o numero do filho (str, possivelmente "" se o Assyst salvou mas
        nao deu para ler o numero) em caso de SUCESSO do salvamento; retorna None
        se qualquer etapa falhou (o chamador retenta na proxima execucao).
        """
        # NOTA SOBRE OS `except Exception` DESTE METODO: sao largos DE PROPOSITO,
        # como no fluxo Selenium original. O Playwright levanta PWTimeout so no
        # caso de espera estourada; violacao de strict mode, elemento que se
        # desprende no meio do clique, navegacao interrompida e target fechado sao
        # `playwright.sync_api.Error`. A porta tinha estreitado para `PWTimeout`, e
        # com isso qualquer um desses furava o metodo, subia pelo `executar()` e
        # matava a RODADA INTEIRA com "Excecao inesperada" — em vez de falhar so a
        # linha, marcar o checkpoint e seguir. Era a rede de seguranca do
        # Desmembramento (checkpoint + retentativa por linha) desligada sem querer.

        # -- DUPLICAR ('Salvar como novo') --
        try:
            self.page.click(_SEL_DUPLICAR, timeout=20000)
            self.log("Clicado em 'Salvar como novo'.", "success")
        except Exception as e:
            if _sessao_expirada_pw(self.page):
                if not _relogin_pw(self.page, numero_chamado, self.usuario, self.senha, self.log):
                    return None
                try:
                    self.page.click(_SEL_DUPLICAR, timeout=20000)
                except Exception as e2:
                    self.log(f"Erro ao duplicar: {e2}", "error")
                    return None
            else:
                self.log(f"Erro ao duplicar: {e}", "error")
                return None

        # -- CONTINUAR --
        if not self._clicar_continuar():
            return None

        # -- DESCRICAO --
        if not _preencher_descricao_pw(self.page, self.log, descricao):
            return None

        # -- SALVAR --
        try:
            self.page.click(_SEL_SALVAR, timeout=20000)
            self.log("Chamado salvo.", "success")
            self.page.wait_for_timeout(2000)
        except Exception as e:
            self.log(f"Erro ao salvar: {e}", "error")
            return None

        # -- CAPTURAR NUMERO DO FILHO -- ("" nao e falha: o chamado foi salvo)
        return _capturar_numero_filho_pw(self.page, self.log)

    def _adicionar_bc(self, kb_function) -> bool:
        """Executa a funcao de KB e retorna True se sucesso.

        A kb_function levanta excecao em falha (regra dos 'sinais reais'); aqui
        ela e convertida em False para o checkpoint nao marcar concluido.
        """
        self.navegacao_perdida = False
        try:
            kb_function(self.page, self.log)
            return True
        except BaseAplicadaSemRetorno as e:
            # A base ESTA no chamado; so a volta a tela do evento falhou. Contar
            # como fracasso deixaria a linha pendente e a proxima execucao
            # aplicaria a MESMA base de novo no mesmo chamado.
            self.log(f"Base aplicada, mas nao voltou a tela do evento: {e}", "error")
            self.navegacao_perdida = True
            return True
        except Exception as e:
            self.log(f"Erro ao adicionar BC: {e}", "error")
            return False


class FluxoCompletoPW(FluxoDesmembramentoPW):
    """Modo Criar + Base: cria o filho (marca SALVO) e aplica a BC (CONCLUIDO)."""

    def executar(self, df, descricao_base: str, numero_chamado: str,
                 kb_function, iniciar_do_zero: bool = False) -> None:
        total = len(df)
        numero_chamado = numero_chamado.strip()
        filhos_novos = []

        # CHECKPOINT — inicializar ou retomar
        if esta_corrompido(numero_chamado):
            self.log(_MSG_CHECKPOINT_ILEGIVEL.format(chave=numero_chamado), "error")
            return
        if iniciar_do_zero or (not existe_pendente(numero_chamado) and not foi_concluido(numero_chamado)):
            self.log("Inicializando checkpoint...", "info")
            inicializar(numero_chamado, total)
        else:
            salvos = sum(1 for i in range(total) if status_linha(numero_chamado, i) == STATUS_SALVO)
            concluidos = sum(1 for i in range(total) if status_linha(numero_chamado, i) == STATUS_CONCLUIDO)
            self.log(f"Retomando execucao: {concluidos} concluidas, {salvos} salvas sem BC, "
                     f"{total - concluidos - salvos} pendentes.", "status")

        # LOGIN E NAVEGACAO
        if not _fazer_login_pw(self.page, self.usuario, self.senha, self.log):
            return
        if not _navegar_para_chamado_pw(self.page, numero_chamado, self.log):
            return

        # LOOP PRINCIPAL
        self.log(f"--- INICIANDO PROCESSAMENTO ({total} linhas) ---", "status")
        for index, row in df.iterrows():
            st = status_linha(numero_chamado, index)
            if st == STATUS_CONCLUIDO:
                self.log(f"Linha {index + 1}/{total}: ja concluida, pulando.", "info")
                continue

            self.log(f"--- Linha {index + 1}/{total} | status: {st} ---", "status")
            if not self._relogar_se_preciso(numero_chamado):
                return

            descricao = _montar_descricao(descricao_base, row)

            # FASE 1 — criar e salvar o chamado
            if st == STATUS_PENDENTE:
                num_filho = self._criar_chamado_filho(numero_chamado, descricao)
                if num_filho is None:
                    self.log(f"Linha {index + 1} nao criada; sera retentada.", "error")
                    _navegar_para_chamado_pw(self.page, numero_chamado, self.log)
                    continue
                if num_filho:
                    _registrar_filho(numero_chamado, num_filho)
                    filhos_novos.append(num_filho)
                marcar_salvo(numero_chamado, index, numero_filho=num_filho)
                self.log(f"Checkpoint: linha {index + 1} marcada como SALVA. Filho: {num_filho}", "info")
            else:
                # Linha ja salva — navegar para o filho para adicionar a BC
                num_filho = numero_filho(numero_chamado, index)
                if num_filho:
                    self.log(f"Linha {index + 1} ja salva. Navegando para o filho {num_filho}...", "status")
                    if not _navegar_para_chamado_pw(self.page, num_filho, self.log):
                        self.log(f"Nao foi possivel acessar o chamado filho {num_filho}.", "error")
                        continue
                else:
                    self.log(f"Linha {index + 1} salva mas numero do filho nao encontrado. Pulando.", "error")
                    continue

            # FASE 2 — adicionar Base de Conhecimento
            if not self._relogar_se_preciso(numero_chamado):
                return
            self.log("Adicionando Base de Conhecimento...", "status")
            bc_ok = self._adicionar_bc(kb_function)
            if bc_ok:
                marcar_concluido_linha(numero_chamado, index)
                self.log(f"Checkpoint: linha {index + 1} marcada como CONCLUIDA.", "success")
            else:
                self.log(f"BC nao adicionada na linha {index + 1}. Sera retentada na proxima execucao.", "error")

            # A cadeia de duplicacao parte do evento ABERTO na tela. Quando a fase
            # da BC nao devolve a tela do evento — a volta falhou, ou a propria BC
            # falhou e deixou a pesquisa de conhecimento aberta — reabrimos o
            # chamado pelo numero. Sem isso a proxima linha tentaria duplicar a
            # partir de uma tela qualquer.
            if self.navegacao_perdida or not bc_ok:
                _navegar_para_chamado_pw(self.page, num_filho or numero_chamado, self.log)

            if not self._relogar_se_preciso(numero_chamado):
                return

        # RESUMO FINAL
        concluidos = sum(1 for i in range(total) if status_linha(numero_chamado, i) == STATUS_CONCLUIDO)
        salvos = sum(1 for i in range(total) if status_linha(numero_chamado, i) == STATUS_SALVO)
        if salvos > 0:
            self.log(f"Execucao finalizada: {concluidos}/{total} concluidas. "
                     f"{salvos} salvas sem BC — execute novamente para completar.", "status")
        else:
            self.log(f"Todos os {total} chamados processados com sucesso!", "success")

        if filhos_novos:
            self.log(f"Abrindo arquivo de chamados filhos ({len(filhos_novos)} novos)...", "info")
            _abrir_txt_filhos(numero_chamado)


class FluxoCriarPW(FluxoDesmembramentoPW):
    """Modo So Criar (3N): apenas duplica os filhos, sem Base de Conhecimento.

    Cada linha vira CONCLUIDA assim que o filho e salvo (nao ha estado SALVO
    intermediario). Sem o log [DEBUG] que ficara pendente no flow_3n Selenium.
    """

    def executar(self, df, descricao_base: str, numero_chamado: str,
                 iniciar_do_zero: bool = False) -> None:
        total = len(df)
        numero_chamado = numero_chamado.strip()
        filhos_novos = []

        # CHECKPOINT
        if esta_corrompido(numero_chamado):
            self.log(_MSG_CHECKPOINT_ILEGIVEL.format(chave=numero_chamado), "error")
            return
        if iniciar_do_zero or (not existe_pendente(numero_chamado) and not foi_concluido(numero_chamado)):
            self.log("Inicializando checkpoint...", "info")
            inicializar(numero_chamado, total)
        else:
            concluidos = sum(1 for i in range(total) if status_linha(numero_chamado, i) == STATUS_CONCLUIDO)
            pendentes = sum(1 for i in range(total) if status_linha(numero_chamado, i) == STATUS_PENDENTE)
            self.log(f"Retomando execucao: {concluidos} concluidas, {pendentes} pendentes.", "status")

        # LOGIN E NAVEGACAO
        if not _fazer_login_pw(self.page, self.usuario, self.senha, self.log):
            return
        if not _navegar_para_chamado_pw(self.page, numero_chamado, self.log):
            return

        # LOOP PRINCIPAL
        self.log(f"--- INICIANDO PROCESSAMENTO 3N ({total} linhas) ---", "status")
        for index, row in df.iterrows():
            st = status_linha(numero_chamado, index)
            if st == STATUS_CONCLUIDO:
                self.log(f"Linha {index + 1}/{total}: ja concluida, pulando.", "info")
                continue

            self.log(f"--- Linha {index + 1}/{total} ---", "status")
            if not self._relogar_se_preciso(numero_chamado):
                return

            descricao = _montar_descricao(descricao_base, row)
            num_filho = self._criar_chamado_filho(numero_chamado, descricao)
            if num_filho is None:
                self.log(f"Linha {index + 1} nao criada; sera retentada.", "error")
                _navegar_para_chamado_pw(self.page, numero_chamado, self.log)
                continue

            if num_filho:
                _registrar_filho(numero_chamado, num_filho)
                filhos_novos.append(num_filho)

            # No 3N, chamado salvo = concluido (nao ha Fase 2)
            marcar_concluido_linha(numero_chamado, index)
            self.log(f"Checkpoint: linha {index + 1} marcada como CONCLUIDA. Filho: {num_filho}", "success")

            if not self._relogar_se_preciso(numero_chamado):
                return

        # RESUMO FINAL
        concluidos = sum(1 for i in range(total) if status_linha(numero_chamado, i) == STATUS_CONCLUIDO)
        pendentes = sum(1 for i in range(total) if status_linha(numero_chamado, i) == STATUS_PENDENTE)
        if pendentes > 0:
            self.log(f"Execucao finalizada: {concluidos}/{total} concluidas. "
                     f"{pendentes} pendentes — execute novamente para completar.", "status")
        else:
            self.log(f"Todos os {total} chamados criados com sucesso!", "success")

        if filhos_novos:
            self.log(f"Abrindo arquivo de chamados filhos ({len(filhos_novos)} novos)...", "info")
            _abrir_txt_filhos(numero_chamado)


class FluxoBCPW(FluxoDesmembramentoPW):
    """Modo So Base: recebe filhos ja criados e aplica a BC em cada um.

    Checkpoint indexado pelo primeiro filho da lista (`bc_<primeiro>`).

    Diferente do modo Criar+Base, aqui NAO se volta a tela do evento depois de
    salvar a base: o passo seguinte e navegar para OUTRO chamado, entao a tela do
    evento seria descartada de qualquer jeito. Quem manda nisso e o
    `voltar_ao_evento=False` que a aba passa ao `executar_kb_unica_pw`.
    """

    def executar(self, filhos: list[str], kb_function,
                 iniciar_do_zero: bool = False) -> None:
        filhos = [f.strip() for f in filhos if f.strip()]
        if not filhos:
            self.log("Nenhum chamado informado.", "error")
            return

        total = len(filhos)
        chave = _chave_checkpoint(filhos)

        # CHECKPOINT
        if esta_corrompido(chave):
            self.log(_MSG_CHECKPOINT_ILEGIVEL.format(chave=chave), "error")
            return
        if iniciar_do_zero or (not existe_pendente(chave) and not foi_concluido(chave)):
            self.log("Inicializando checkpoint BC...", "info")
            inicializar(chave, total)
        else:
            concluidos = sum(1 for i in range(total) if status_linha(chave, i) == STATUS_CONCLUIDO)
            self.log(f"Retomando execucao BC: {concluidos} concluidas, {total - concluidos} pendentes.", "status")

        # LOGIN
        if not _fazer_login_pw(self.page, self.usuario, self.senha, self.log):
            return

        # LOOP PRINCIPAL
        self.log(f"--- INICIANDO PROCESSAMENTO BC ({total} chamados) ---", "status")
        for index, numero_filho_str in enumerate(filhos):
            st = status_linha(chave, index)
            if st == STATUS_CONCLUIDO:
                self.log(f"Chamado {index + 1}/{total} ({numero_filho_str}): ja concluido, pulando.", "info")
                continue

            self.log(f"--- Chamado {index + 1}/{total}: {numero_filho_str} ---", "status")
            # Fluxo BC nao tem 'chamado pai' fixo: reloga sem navegar (o proximo
            # passo ja navega para o filho da vez).
            if not self._relogar_se_preciso():
                return

            if not _navegar_para_chamado_pw(self.page, numero_filho_str, self.log):
                self.log(f"Nao foi possivel acessar {numero_filho_str}. Pulando.", "error")
                continue

            if not self._relogar_se_preciso():
                return

            self.log("Adicionando Base de Conhecimento...", "status")
            if self._adicionar_bc(kb_function):
                marcar_concluido_linha(chave, index)
                self.log(f"Checkpoint: {numero_filho_str} marcado como CONCLUIDO.", "success")
            else:
                self.log(f"BC nao adicionada em {numero_filho_str}. Sera retentada na proxima execucao.", "error")

            if not self._relogar_se_preciso():
                return

        # RESUMO FINAL
        concluidos = sum(1 for i in range(total) if status_linha(chave, i) == STATUS_CONCLUIDO)
        if total - concluidos > 0:
            self.log(f"Execucao BC finalizada: {concluidos}/{total} concluidas. "
                     f"{total - concluidos} pendentes — execute novamente para completar.", "status")
        else:
            self.log(f"Base de Conhecimento adicionada em todos os {total} chamados!", "success")
