"""
services/agente/llm.py — Cliente das plataformas de IA, sem pacote novo.

O TÉCNICO ESCOLHE O MODELO no seletor do chat (2026-10-02), como no Claude e
no ChatGPT. Não há troca automática no meio do caminho (decisão do usuário):
se o modelo escolhido falhar ou bater no limite, a mensagem diz isso e
sugere trocar no seletor.

Catálogo em `MODELOS`. Todas as plataformas daqui falam o formato da OpenAI
(/chat/completions com `tools`), então a conversa e o histórico servem para
qualquer uma — trocar de modelo no meio da conversa funciona.
  - Groq (groq.com, chave `gsk_`) — com Q, não a Grok da xAI. Muito rápida;
    plano grátis com limite por minuto E por dia.
  - Gemini (Google AI Studio; chave `AQ.`/`AIza`) — endpoint compatível com OpenAI.
    No plano GRÁTIS o Google pode usar o que é enviado para melhorar os
    produtos dele (aviso dado ao usuário, LGPD).

urllib em vez de requests pelo mesmo motivo do updater: o proxy TLS do TJCE
reassina os certificados, e o urllib usa o repositório de certificados do
Windows, onde a CA corporativa está (ver services/update_service.py).
Conexão com a Groq testada da rede do TJCE em 2026-09-29.

As CHAVES ficam no Cofre de Credenciais do Windows (keyring), uma por
plataforma — nunca no banco, em arquivo ou no git. O modelo ESCOLHIDO (só o
id, sem segredo) fica no banco (app_config 'modelo_ia').
"""

import dataclasses
import json
import time
import urllib.error
import urllib.request

import keyring

_SERVICO = "Automatic-IA"


@dataclasses.dataclass(frozen=True)
class Plataforma:
    """Quem fornece a chave. A página API Keys desenha um cartão por
    plataforma a partir daqui (08/10): plataforma nova = uma entrada aqui +
    o(s) modelo(s) dela em MODELOS — sem mexer na página nem no state."""
    id: str            # o "usuário" da chave no Cofre do Windows
    nome: str
    link: str          # onde o técnico cria a chave
    ajuda: str
    placeholder: str
    prefixo: str = ""  # conferido ao salvar ("" = sem conferência)
    aviso: str = ""    # ex.: uso dos dados no plano grátis (LGPD)


PLATAFORMAS: dict[str, Plataforma] = {p.id: p for p in [
    Plataforma("groq", "Groq", "https://console.groq.com/keys",
               "Cada técnico usa a sua. Crie em console.groq.com → API Keys.",
               "gsk_...", prefixo="gsk_"),
    # Sem prefixo: o Google tem mais de um formato de chave (a do usuário
    # começa com "AQ.", não "AIza" — 02/10). Quem confere de verdade é a
    # primeira chamada ao modelo.
    Plataforma("gemini", "Gemini (Google)", "https://aistudio.google.com/apikey",
               "Opcional. Crie em aistudio.google.com → Get API key.",
               "chave do Google AI Studio"),
]}


@dataclasses.dataclass(frozen=True)
class Modelo:
    id: str            # o que fica gravado como escolha
    rotulo: str        # o que aparece no seletor
    plataforma: str    # id em PLATAFORMAS (e o "usuário" da chave no Cofre)
    url: str
    modelo: str        # nome do modelo na API da plataforma


MODELOS: dict[str, Modelo] = {m.id: m for m in [
    Modelo("groq", "Groq · GPT-OSS 120B", "groq",
           "https://api.groq.com/openai/v1/chat/completions",
           # gpt-oss-120b: suporta ferramentas e extraiu certo os pedidos em
           # português nos testes (~1 s por resposta).
           "openai/gpt-oss-120b"),
    Modelo("gemini", "Gemini · Flash Lite", "gemini",
           "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
           # Apelido "lite-latest" (sempre o Flash Lite mais novo): o Google
           # aposenta modelos (o 2.5-flash deu 404 "no longer available" em
           # 02/10) e o Flash cheio estava sobrecarregado (503). Testado em
           # 02/10: ~1,6 s, chamou DUAS ferramentas numa resposta só e acertou
           # os pedidos de plano, Requisição e Resolver (com SLA antes).
           "gemini-flash-lite-latest"),
]}
PADRAO = "groq"

# Compatibilidade: quem ainda usa llm.MODELO/URL (ex.: scripts de teste).
MODELO = MODELOS[PADRAO].modelo
URL = MODELOS[PADRAO].url


class ErroLLM(Exception):
    """Falha ao falar com a API — a mensagem já vem pronta para o técnico ler."""


# --------------------------------------------------------------------------- #
# Chaves (Cofre do Windows) e modelo escolhido
# --------------------------------------------------------------------------- #

def carregar_chave(plataforma: str = "groq") -> str:
    return keyring.get_password(_SERVICO, plataforma) or ""


def salvar_chave(chave: str, plataforma: str = "groq") -> None:
    chave = chave.strip()
    if not chave:
        raise ValueError("Chave vazia.")
    keyring.set_password(_SERVICO, plataforma, chave)


def disponiveis() -> list[str]:
    """Ids dos modelos com chave cadastrada nesta máquina."""
    return [m.id for m in MODELOS.values() if carregar_chave(m.plataforma)]


def modelo_escolhido() -> str:
    """O modelo do seletor: o último escolhido, se ainda tiver chave; senão o
    primeiro disponível; senão o padrão."""
    from services import db
    r = db.consultar("SELECT valor FROM app_config WHERE chave = 'modelo_ia'")
    escolhido = r[0]["valor"] if r else PADRAO
    ok = disponiveis()
    if escolhido in ok or not ok:
        return escolhido if escolhido in MODELOS else PADRAO
    return ok[0]


def escolher_modelo(modelo_id: str) -> None:
    if modelo_id not in MODELOS:
        raise ValueError(f"Modelo desconhecido: {modelo_id}")
    from services import db
    with db.transacao() as con:
        con.execute("INSERT OR REPLACE INTO app_config VALUES ('modelo_ia', ?)",
                    (modelo_id,))


# --------------------------------------------------------------------------- #
# Conversa
# --------------------------------------------------------------------------- #

def _msg_limite(m: Modelo, detalhe: str) -> str:
    """Diz QUAL limite foi atingido. Antes toda recusa virava "tente de novo
    em um minuto" — e o limite DIÁRIO da Groq só volta no dia seguinte."""
    d = detalhe.lower()
    if "per day" in d or "daily" in d or "tpd" in d or "rpd" in d:
        return (f"O limite DIÁRIO do {m.rotulo} acabou (plano grátis). Troque o "
                "modelo no seletor do chat ou tente amanhã.")
    return (f"O {m.rotulo} atingiu o limite por minuto. Tente de novo em "
            "instantes ou troque o modelo no seletor do chat.")


def conversar(mensagens: list[dict], ferramentas: list[dict],
              modelo_id: str = PADRAO) -> dict:
    """Uma chamada ao modelo escolhido. Devolve a `message` da resposta (com
    `content` e/ou `tool_calls`)."""
    m = MODELOS.get(modelo_id) or MODELOS[PADRAO]
    chave = carregar_chave(m.plataforma)
    if not chave:
        raise ErroLLM(f"Não há chave do {m.rotulo} cadastrada (Opções → API Keys).")
    corpo = {
        "model": m.modelo,
        "messages": mensagens,
        "tools": ferramentas,
        "tool_choice": "auto",
        "temperature": 0.2,
    }
    req = urllib.request.Request(
        m.url,
        data=json.dumps(corpo).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {chave}",
            "Content-Type": "application/json",
            "User-Agent": "Automatic",
        },
    )
    detalhe = ""
    for tentativa in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                dados = json.load(resp)
            msg = dados["choices"][0]["message"]
            # Tokens gastos nesta ida (formato OpenAI: prompt_tokens /
            # completion_tokens) — para o registro dos pedidos. Chave com "_":
            # o assistente.py monta a mensagem que volta à IA sem ela.
            msg["_uso"] = dados.get("usage") or {}
            return msg
        except urllib.error.HTTPError as e:
            detalhe = e.read()[:400].decode("utf-8", "replace")
            if e.code in (401, 403):
                raise ErroLLM(f"A chave do {m.rotulo} foi recusada ({e.code}). "
                              "Confira em Opções → API Keys.") from e
            if (e.code == 400 and tentativa < 2
                    and ("output_parse_failed" in detalhe or "tool_use_failed" in detalhe)):
                # O modelo gerou uma chamada de ferramenta mal formada (visto em
                # 01/10, esporádico). Gerar de novo costuma sair certo.
                continue
            if e.code in (500, 502, 503, 504):
                # Plataforma sobrecarregada (o Gemini devolveu 503 "high demand"
                # em 02/10). Costuma ser passageiro: tenta de novo uma vez.
                if tentativa < 1:
                    time.sleep(3)
                    continue
                raise ErroLLM(f"O {m.rotulo} está sobrecarregado agora. Tente de "
                              "novo em instantes ou troque o modelo no seletor do chat.") from e
            if e.code == 429:
                d = detalhe.lower()
                diario = "per day" in d or "daily" in d or "tpd" in d or "rpd" in d
                # Limite POR MINUTO: espera o que a API pedir (até 20 s) e tenta
                # de novo, até 2 vezes. O DIÁRIO não adianta esperar.
                if tentativa < 2 and not diario:
                    try:
                        espera = float(e.headers.get("retry-after", "5"))
                    except ValueError:
                        espera = 5.0
                    time.sleep(min(max(espera, 1.0), 20.0))
                    continue
                raise ErroLLM(_msg_limite(m, detalhe)) from e
            raise ErroLLM(f"O {m.rotulo} respondeu com erro {e.code}: {detalhe}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            raise ErroLLM(f"Não consegui falar com o {m.rotulo}: {e}") from e
    raise ErroLLM(_msg_limite(m, detalhe))
