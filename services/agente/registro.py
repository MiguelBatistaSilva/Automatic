"""
services/agente/registro.py — Registro dos pedidos ao Assistente (08/10).

Uma linha por pedido na tabela `agente_pedidos` (services/db.py, v8): o que
o técnico pediu, que domínio o roteador escolheu, que ferramentas a IA
chamou e com quê, idas/tokens/tempo, o que o técnico fez com o cartão e o
resultado de cada passo.

Para quê (conversa de 07-08/10): diagnosticar quando o Assistente erra,
estudar como os técnicos pedem (frase real que errou vira caso do
eval_roteador.py) e medir. Leitura: `python relatorio_agente.py`.

Regras:
  - NUNCA derruba o Assistente: toda função engole o próprio erro (registro
    é acessório; perder uma linha é melhor que perder o pedido).
  - Só nesta máquina (banco local em %LOCALAPPDATA%), nunca vai para fora.
  - Apagado sozinho depois de `DIAS_RETENCAO` dias (LGPD: os pedidos citam
    nomes de usuários e números de chamado).
  - Senha/chave nunca passa por aqui; `_limpar` corta por garantia qualquer
    argumento com nome suspeito.
"""

import datetime
import json

DIAS_RETENCAO = 30

_SUSPEITOS = ("senha", "password", "chave", "token", "secret", "api_key")


def _agora() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _limpar(valor):
    """Cópia sem nenhum campo de nome suspeito (em qualquer profundidade)."""
    if isinstance(valor, dict):
        return {k: ("***" if any(s in k.lower() for s in _SUSPEITOS) else _limpar(v))
                for k, v in valor.items()}
    if isinstance(valor, list):
        return [_limpar(v) for v in valor]
    return valor


def _json(valor) -> str:
    return json.dumps(_limpar(valor), ensure_ascii=False, default=str)


def _apagar_antigos(con) -> None:
    limite = (datetime.datetime.now()
              - datetime.timedelta(days=DIAS_RETENCAO)).isoformat(timespec="seconds")
    con.execute("DELETE FROM agente_pedidos WHERE quando < ?", (limite,))


def gravar_pedido(matricula: str, modelo: str, pedido: str, resposta=None,
                  desfecho: str = "", erro: str = "") -> int | None:
    """Grava o pedido logo depois da resposta da IA. `resposta` é o
    `assistente.Resposta` (None quando a IA deu erro). Devolve o id da linha
    (para o desfecho e o resultado chegarem depois) ou None se não gravou."""
    try:
        from services import db
        m = getattr(resposta, "metricas", None) or {}
        acoes = getattr(resposta, "acoes", None) or []
        with db.transacao() as con:
            _apagar_antigos(con)
            cur = con.execute(
                "INSERT INTO agente_pedidos (quando, matricula, modelo, pedido, dominios,"
                " rede, idas, tokens_entrada, tokens_saida, ms, chamadas, resposta,"
                " plano, desfecho, erro) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (_agora(), matricula or "", modelo or "", pedido or "",
                 m.get("dominios", ""), int(bool(m.get("rede"))), m.get("idas", 0),
                 m.get("tokens_entrada", 0), m.get("tokens_saida", 0), m.get("ms", 0),
                 _json(m.get("chamadas", [])), getattr(resposta, "texto", "") or "",
                 " | ".join(a.titulo for a in acoes), desfecho, erro))
            return cur.lastrowid
    except Exception:
        return None


def marcar_desfecho(id_pedido: int | None, desfecho: str) -> None:
    """O que o técnico fez com o cartão (confirmou, simulou, cancelou...)."""
    if not id_pedido:
        return
    try:
        from services import db
        with db.transacao() as con:
            con.execute("UPDATE agente_pedidos SET desfecho = ? WHERE id = ?",
                        (desfecho, id_pedido))
    except Exception:
        pass


def gravar_resultado(id_pedido: int | None, resultados: list[dict], erro: str = "") -> None:
    """Resultado de cada passo executado: [{passo, ok, texto}]."""
    if not id_pedido:
        return
    try:
        from services import db
        with db.transacao() as con:
            con.execute("UPDATE agente_pedidos SET resultado = ?, erro = ? WHERE id = ?",
                        (_json(resultados), erro, id_pedido))
    except Exception:
        pass
