"""
flow_runner.py — A ponte async (Reflex) <-> sync (Playwright).

E o coracao reutilizavel de TODAS as abas migradas. Os fluxos em `services/`
rodam Playwright SYNC e chamam `log(msg, tipo)` de dentro de uma thread; o Reflex
e async e transmite estado ao navegador via WebSocket. Esta ponte substitui 1:1
o par `log_signal`/`_append_log` do PyQt6:

  1. o fluxo sync roda numa thread dedicada (como o QThread fazia);
  2. o `log` empurra a mensagem numa asyncio.Queue via `call_soon_threadsafe`
     (unica forma segura de falar com o loop async a partir de outra thread);
  3. o evento background da `await fila.get()` num laco, atualiza `self.logs`
     dentro de `async with self:` e faz `yield` — cada yield transmite ao vivo;
  4. um sentinela `None` (emitido no `finally` da thread) encerra o laco.

Subclasses expoem um `@rx.event(background=True)` que monta a `worker_fn(log)`
com o fluxo sync e faz `async for _ in self._rodar_sync(worker_fn): yield`.

ATENCAO — E UM **MIXIN** (`mixin=True`), nao um state normal, e as paginas o usam
como `class XState(FlowRunnerState, rx.State)`. Motivo: var HERDADA em Reflex e
COMPARTILHADA (mora no state pai), entao com heranca normal License, SLA,
Desmembramento e Atendimento dividiam a MESMA lista `logs` e o mesmo `rodando` — o
log de uma pagina aparecia na outra. Com mixin, cada state ganha a sua COPIA das
vars. As duas formas compilam; so a do mixin isola.
Cuidado: `class XState(FlowRunnerState)` sozinho NAO funciona (as vars do mixin
somem) — o `rx.State` tem que estar nas bases.
"""

import asyncio
import dataclasses
import threading
import time

import reflex as rx


@dataclasses.dataclass
class LogLine:
    """Uma linha de log TIPADA.

    Precisa ser tipada (dataclass, nao dict) para que no front `item.ts`/`item.msg`
    sejam Vars `str` — Var sem tipo (vinda de dict) nao suporta concatenacao de
    string e quebra o `rx.foreach` na compilacao.
    """

    ts: str
    tipo: str
    msg: str


class FlowRunnerState(rx.State, mixin=True):
    logs: list[LogLine] = []
    rodando: bool = False

    def _linha(self, msg: str, tipo: str) -> LogLine:
        return LogLine(ts=time.strftime("%H:%M:%S"), tipo=tipo, msg=msg)

    async def _rodar_sync(self, worker_fn, on_evento=None):
        """Async generator: roda `worker_fn(log, emit)` numa thread e faz stream.

        `worker_fn(log, emit)` contem todo o fluxo sync (NavegadorPW + services):
          - `log(msg, tipo="info")` -> vira uma linha no console de logs;
          - `emit(kind, payload)`   -> evento arbitrario (ex.: uma linha de tabela).
        Ambos sao thread-safe. NUNCA acessar `self` de dentro de `worker_fn`: ela
        roda noutra thread; passe os dados por closure.

        `on_evento(kind, payload)` (async, opcional) trata os eventos que NAO sao
        log — a subclasse usa para, ex., anexar um resultado na tabela. Os logs sao
        tratados aqui na base (mesmo caminho ja provado na aba License).

        O padrao no evento background da subclasse:
            async for _ in self._rodar_sync(worker, on_evento=self._on_evento):
                yield
        """
        loop = asyncio.get_running_loop()
        fila: asyncio.Queue = asyncio.Queue()

        def emit(kind, payload):
            loop.call_soon_threadsafe(fila.put_nowait, (kind, payload))

        def log(msg, tipo="info"):
            emit("log", (msg, tipo))

        def runner():
            try:
                worker_fn(log, emit)
            except Exception as e:  # espelha o try/except dos workers Qt
                emit("log", (f"Excecao inesperada: {e}", "error"))
            finally:
                loop.call_soon_threadsafe(fila.put_nowait, None)  # sentinela

        # Thread dedicada (nao o executor pool): fresca a cada execucao, igual ao
        # QThread. Importa para o Playwright sync, que se prende a thread que o criou.
        threading.Thread(target=runner, daemon=True).start()

        while True:
            item = await fila.get()
            if item is None:
                break
            kind, payload = item
            if kind == "log":
                msg, tipo = payload
                async with self:
                    self.logs = self.logs + [self._linha(msg, tipo)]
            elif on_evento is not None:
                await on_evento(kind, payload)
            yield
