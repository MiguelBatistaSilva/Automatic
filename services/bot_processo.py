"""
services/bot_processo.py — Liga e desliga o bot do Telegram pelo app (06/11).

Antes era o iniciar_bot.bat, com o terminal próprio. Agora o backend do Reflex sobe
o bot como processo filho, sem janela, e guarda a saída para a tela do Assistente
mostrar (é nela que se vê o chat_id de quem pediu acesso).

O BOT MORRE COM O APP: o filho fica lendo o stdin, que é um pipe aberto pelo pai.
Se o app fechar, mesmo à força, o pipe fecha e o filho encerra. Sem isso, um bot
sem janela ficaria de pé sem ninguém conseguir desligar, e o atualizar_automatic.bat
se recusaria a rodar (ver `_app_aberto` em atualizar.py).

LIGA SOZINHO: quem ligou o bot deixa `bot_ligado` no banco, e ele volta quando o
app abrir de novo. Sem credencial nenhuma aqui: o próprio bot lê o token do cofre.
"""

import collections
import os
import re
import subprocess
import sys
import threading

from services.dados import db
from services.paths import PROJECT_ROOT

_CHAVE = "bot_ligado"
_COMANDO = [sys.executable, "-u", "-m", "bot.main", "--filho-do-app"]
# O httpx está silenciado em bot/comum.py, mas o erro de uma biblioteca pode trazer
# a URL, que tem o token. A saída vai para o navegador: nunca deixar passar.
_TOKEN = re.compile(r"\d{6,}:[A-Za-z0-9_-]{20,}")

_lock = threading.Lock()
_processo: "subprocess.Popen | None" = None
_linhas: "collections.deque[str]" = collections.deque(maxlen=500)


def _gravar_ligado(ligado: bool) -> None:
    with db.transacao() as con:
        con.execute("INSERT OR REPLACE INTO app_config VALUES (?, ?)",
                    (_CHAVE, "1" if ligado else "0"))


def _ler(processo: subprocess.Popen) -> None:
    for linha in processo.stdout:
        _linhas.append(_TOKEN.sub("***", linha.rstrip()))
    _linhas.append(f"Bot encerrado (código {processo.wait()}).")


def ligado() -> bool:
    return _processo is not None and _processo.poll() is None


def linhas() -> list[str]:
    return list(_linhas)


def tem_token() -> bool:
    from bot.services import credencial_servico
    return bool(credencial_servico.carregar_token())


def ligar() -> str:
    """Devolve o erro, ou "" se ligou (ou já estava ligado)."""
    global _processo
    with _lock:
        if ligado():
            return ""
        if not tem_token():
            return "Cadastre o token do bot em Opções → API Keys."
        try:
            _processo = subprocess.Popen(
                _COMANDO, cwd=PROJECT_ROOT,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                encoding="utf-8", errors="replace",
                env={**os.environ, "PYTHONUTF8": "1"},
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except OSError as e:
            return f"Não consegui ligar o bot: {e}"
        threading.Thread(target=_ler, args=(_processo,), daemon=True).start()
        _gravar_ligado(True)
        return ""


def desligar() -> None:
    with _lock:
        _gravar_ligado(False)
        if not ligado():
            return
        _processo.stdin.close()   # o filho vê o fim do pipe e encerra
        try:
            _processo.wait(5)
        except subprocess.TimeoutExpired:
            _processo.kill()


def retomar() -> None:
    """Ao subir o app: liga de novo se estava ligado."""
    if any(r["valor"] == "1" for r in
           db.consultar("SELECT valor FROM app_config WHERE chave = ?", (_CHAVE,))):
        ligar()


def morrer_com_o_pai() -> None:
    """Chamado no bot: encerra quando o pipe do stdin fechar."""
    def vigiar():
        try:
            while sys.stdin.read(1024):
                pass
        finally:
            os._exit(0)

    threading.Thread(target=vigiar, daemon=True).start()
