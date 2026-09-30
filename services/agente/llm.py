"""
services/agente/llm.py — Cliente da Groq (groq.com), sem pacote novo.

Groq, com Q — não a Grok da xAI. A chave `gsk_...` é da Groq (confirmado em
2026-09-29). A API é compatível com a da OpenAI (/chat/completions com `tools`).

urllib em vez de requests pelo mesmo motivo do updater: o proxy TLS do TJCE
reassina os certificados, e o urllib usa o repositório de certificados do
Windows, onde a CA corporativa está (ver services/update_service.py).
Conexão testada da rede do TJCE em 2026-09-29.

A CHAVE fica no Cofre de Credenciais do Windows (keyring), como a senha do
Assyst — nunca no banco, em arquivo ou no git.
"""

import json
import time
import urllib.error
import urllib.request

import keyring

URL = "https://api.groq.com/openai/v1/chat/completions"
# Sem preferência do usuário. gpt-oss-120b: suporta ferramentas e extraiu
# certo um pedido de desmembramento em português no teste (0,9 s).
MODELO = "openai/gpt-oss-120b"

_SERVICO = "Automatic-IA"
_USUARIO = "groq"


class ErroLLM(Exception):
    """Falha ao falar com a API — a mensagem já vem pronta para o técnico ler."""


def carregar_chave() -> str:
    return keyring.get_password(_SERVICO, _USUARIO) or ""


def salvar_chave(chave: str) -> None:
    chave = chave.strip()
    if not chave:
        raise ValueError("Chave vazia.")
    keyring.set_password(_SERVICO, _USUARIO, chave)


def conversar(mensagens: list[dict], ferramentas: list[dict]) -> dict:
    """Uma chamada ao modelo. Devolve a `message` da resposta (com `content`
    e/ou `tool_calls`)."""
    chave = carregar_chave()
    if not chave:
        raise ErroLLM("A chave da IA não está configurada.")
    corpo = {
        "model": MODELO,
        "messages": mensagens,
        "tools": ferramentas,
        "tool_choice": "auto",
        "temperature": 0.2,
    }
    req = urllib.request.Request(
        URL,
        data=json.dumps(corpo).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {chave}",
            "Content-Type": "application/json",
            "User-Agent": "Automatic",
        },
    )
    for tentativa in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                dados = json.load(resp)
            return dados["choices"][0]["message"]
        except urllib.error.HTTPError as e:
            detalhe = e.read()[:300].decode("utf-8", "replace")
            if e.code == 401:
                raise ErroLLM("A chave da IA foi recusada (401). Confira a chave.") from e
            if e.code == 429:
                # Plano gratuito: 8.000 tokens/minuto (visto em 2026-09-29) e
                # cada chamada leva ~1.000 so com as ferramentas. A API diz
                # quanto esperar; espera e tenta de novo, ate 2 vezes.
                if tentativa < 2:
                    try:
                        espera = float(e.headers.get("retry-after", "5"))
                    except ValueError:
                        espera = 5.0
                    time.sleep(min(max(espera, 1.0), 20.0))
                    continue
                raise ErroLLM("Limite de uso da IA atingido. Tente de novo em "
                              "um minuto.") from e
            raise ErroLLM(f"A IA respondeu com erro {e.code}: {detalhe}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            raise ErroLLM(f"Não consegui falar com a IA: {e}") from e
    raise ErroLLM("Limite de uso da IA atingido. Tente de novo em um minuto.")
