"""
services/agente/sessao.py — Uma sessão do Assyst para um PLANO inteiro.

Antes cada ferramenta abria o próprio Chrome (via bot/services/*) e fazia
login. Num plano de vários passos isso seria um login e uma licença por
passo. Aqui o navegador abre na primeira vez que um passo pede a página e
é fechado no fim do plano — todos os passos usam a mesma sessão.

Os fluxos (services/flow_*_pw.py) já recebem a página pronta, então nenhum
arquivo de fluxo mudou para isto (2026-10-01).

ATENÇÃO: o Playwright sync se prende à thread que o criou. Criar, usar e
fechar a Sessao na MESMA thread (a do executor do plano).
"""

import dataclasses

from services.browser_pw import NavegadorPW, _fazer_login_pw


class ErroSessao(Exception):
    """Não deu para abrir/logar — a mensagem vai para o técnico."""


@dataclasses.dataclass
class Resultado:
    texto: str        # markdown que aparece na conversa
    ok: bool = True   # False interrompe o plano (os passos seguintes não rodam)


class Sessao:
    def __init__(self, matricula: str, senha: str, log,
                 modo_teste: bool = False, iniciar_do_zero: bool = False):
        self.matricula = matricula
        self.senha = senha
        self.log = log
        self.modo_teste = modo_teste
        self.iniciar_do_zero = iniciar_do_zero
        self._nav = None
        self._page = None

    def pagina(self):
        """A página logada. Abre o navegador e loga só na primeira chamada."""
        if self._page is None:
            self._nav = NavegadorPW(self.log)
            self._page = self._nav.__enter__()
            if not _fazer_login_pw(self._page, self.matricula, self.senha, self.log):
                raise ErroSessao("Falha no login do Assyst.")
        return self._page

    def fechar(self):
        if self._nav is not None:
            try:
                self._nav.__exit__(None, None, None)
            finally:
                self._nav = self._page = None


def executar_plano(acoes, sessao: Sessao, executar, emitir) -> None:
    """Roda os passos EM FILA na mesma sessão e fecha o navegador no fim.

    `executar(acao, sessao) -> Resultado` roda um passo; `emitir(tipo, dado)`
    avisa quem acompanha: ("passo", (i, "rodando"|"pulado")), ("resultado",
    (i, Resultado)) e ("fim", None) — este SEMPRE, mesmo com exceção.
    Passo que falha (ok=False) interrompe o plano: os seguintes viram "pulado"
    — no fluxo de investigação, o passo seguinte depende do anterior.
    """
    try:
        for i, acao in enumerate(acoes):
            emitir("passo", (i, "rodando"))
            try:
                r = executar(acao, sessao)
            except Exception as e:
                r = Resultado(f"Erro inesperado em '{acao.titulo}': {e}", ok=False)
            emitir("resultado", (i, r))
            if not r.ok:
                for j in range(i + 1, len(acoes)):
                    emitir("passo", (j, "pulado"))
                break
    finally:
        try:
            sessao.fechar()
        finally:
            emitir("fim", None)
