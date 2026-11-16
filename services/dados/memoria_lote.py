"""
services/dados/memoria_lote.py — Memória (checkpoint) dos lotes que não
tinham (16/11): Adicionar Itom, Importar documento e Corrigir Item B do
Desmembramento, e corrigir_chamado / corrigir_item_b / anexar_itom do agente.

Mesmas tabelas do checkpoint (services/dados/checkpoint.py), então a rodada
aparece em "Meus fluxos". A chave é <prefixo>_<hash dos itens>, como o bc_ do
Só Base: a MESMA lista é o MESMO lote. Linha concluída não é refeita; linha
com erro fica pendente para a próxima vez.

Os fluxos (services/fluxos/) não mudaram: quem chama filtra os já feitos
antes e marca o que terminou.
"""

import hashlib

from services.dados import checkpoint

PENDENTE, CONCLUIDO, NOVO = "pendente", "concluido", "novo"


def chave(prefixo: str, itens: list[str]) -> str:
    h = hashlib.sha1("\n".join(itens).encode("utf-8")).hexdigest()[:16]
    return f"{prefixo}_{h}"


def situacao(k: str) -> str:
    """pendente | concluido | novo — para o diálogo/cartão decidir os botões."""
    if checkpoint.existe_pendente(k):
        return PENDENTE
    if checkpoint.foi_concluido(k):
        return CONCLUIDO
    return NOVO


def abrir(k: str, itens: list[str], referencias: list[str], *, fluxo: str,
          origem: str, matricula: str = "", do_zero: bool = False) -> set[int]:
    """Índices JÁ feitos. Lote pela metade (e sem do_zero) = retoma; lote
    novo, concluído ou do_zero = rodada nova (a anterior fica no histórico)."""
    if not do_zero and checkpoint.existe_pendente(k):
        return {l["index"] for l in checkpoint.status_linhas(k)
                if l["status"] == checkpoint.STATUS_CONCLUIDO}
    checkpoint.inicializar(k, len(itens), fluxo=fluxo, origem=origem,
                           matricula=matricula, referencias=referencias)
    return set()


def marcar(k: str, indice: int, **extra) -> None:
    checkpoint.marcar_concluido_linha(k, indice, **extra)


def resumo(k: str) -> str:
    return checkpoint.resumo(k)


# --------------------------------------------------------------------------- #
# Dados do lote — o "Retomar" da página "Meus fluxos" (16/11)
# --------------------------------------------------------------------------- #
#
# O checkpoint guarda só o andamento ("linha 3 pendente"). Para rodar de novo
# é preciso o que a tela do Desmembramento tinha: modo, base, descrição, CSV,
# chamados/tombos, PDF. Fica na tabela `lotes` (banco v10), pela chave.

def guardar_parametros(k: str, parametros: dict) -> None:
    import json
    from services.dados import db
    with db.transacao() as con:
        con.execute(
            "INSERT INTO lotes (chave, parametros, atualizado_em) "
            "VALUES (?, ?, datetime('now', 'localtime')) "
            "ON CONFLICT(chave) DO UPDATE SET parametros = excluded.parametros, "
            "atualizado_em = excluded.atualizado_em",
            (k, json.dumps(parametros, ensure_ascii=False)))


def parametros(k: str) -> dict | None:
    import json
    from services.dados import db
    with db.leitura() as con:
        r = con.execute("SELECT parametros FROM lotes WHERE chave = ?", (k,)).fetchone()
    return json.loads(r["parametros"]) if r else None


def chaves_com_parametros(chaves: list[str]) -> set[str]:
    from services.dados import db
    if not chaves:
        return set()
    with db.leitura() as con:
        rows = con.execute(
            f"SELECT chave FROM lotes WHERE chave IN ({','.join('?' * len(chaves))})",
            chaves).fetchall()
    return {r["chave"] for r in rows}
