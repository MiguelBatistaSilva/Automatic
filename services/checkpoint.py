"""
services/checkpoint.py — Gerencia o progresso linha a linha com 3 estados:
  pendente  → ainda nao processada
  salvo     → chamado criado mas BC ainda nao adicionada
  concluido → chamado criado + BC adicionada

ONDE MORA: tabelas `checkpoints` e `checkpoint_linhas` do banco
(services/db.py) desde 2026-09-28. Antes era um JSON por chave em
data/checkpoints/<chave>/<chave>.json — importado pelo db.py na subida e
renomeado para .json.migrado. O TXT de filhos (assyst_common) continua em
arquivo: e o relatorio que abre no Bloco de Notas, nao a rede de seguranca.

O que o banco resolveu do formato antigo: cada marcacao e uma transacao (nao
existe mais "JSON pela metade" nem a gravacao atomica via .tmp.json, que
disparava o hot-reload do Reflex), e bot + UI podem marcar ao mesmo tempo sem
um apagar a marcacao do outro.

A interface (nomes, argumentos e o formato dict das linhas) NAO mudou —
os tres modos do Desmembramento, a Requisicao e o bot nao foram tocados.
"""
import json
from datetime import datetime

from services import db
from services.paths import CHECKPOINTS_DIR as _CHECKPOINTS_DIR

STATUS_PENDENTE  = "pendente"
STATUS_SALVO     = "salvo"
STATUS_CONCLUIDO = "concluido"


def _agora() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def _rodada(con, chave: str) -> int | None:
    """Id da rodada VIGENTE da chave — a mais recente. As anteriores sao so
    historico (pagina "Meus fluxos"); nenhuma funcao de retomada olha para elas."""
    r = con.execute("SELECT id FROM checkpoints WHERE chave = ? "
                    "ORDER BY id DESC LIMIT 1", (chave,)).fetchone()
    return r["id"] if r else None


def inicializar(numero_chamado: str, total: int, *, fluxo: str = "",
                origem: str = "", matricula: str = "",
                referencias: list[str] | None = None) -> None:
    """Abre uma rodada NOVA com todas as linhas como pendente — e o "Do zero"
    dos dialogos. A rodada anterior da mesma chave NAO e apagada (desde
    2026-09-29): fica no historico, e a nova passa a ser a vigente.

    `fluxo`/`origem` ('ui'/'bot')/`matricula` identificam a rodada na pagina
    "Meus fluxos". `referencias[i]` e o chamado da linha i, quando conhecido
    de antemao (modo So Base: a chave e um hash, sem ela nao se sabe quem e quem).
    """
    agora = _agora()
    refs = list(referencias or [])
    refs += [""] * (total - len(refs))
    with db.transacao() as con:
        cid = con.execute(
            "INSERT INTO checkpoints (chave, fluxo, origem, matricula, total, "
            "criado_em, atualizado_em, concluido) VALUES (?, ?, ?, ?, ?, ?, ?, 0)",
            (numero_chamado, fluxo, origem, matricula, total, agora, agora)
        ).lastrowid
        con.executemany(
            "INSERT INTO checkpoint_linhas (checkpoint_id, idx, status, referencia) "
            "VALUES (?, ?, ?, ?)",
            [(cid, i, STATUS_PENDENTE, refs[i]) for i in range(total)])


def _atualizar_linha(con, cid, index, status, numero_filho=None,
                     **extra) -> bool:
    r = con.execute(
        "SELECT extra FROM checkpoint_linhas WHERE checkpoint_id = ? AND idx = ?",
        (cid, index)).fetchone()
    if r is None:
        return False
    dados = json.loads(r["extra"])
    dados.update(extra)
    if numero_filho is None:
        con.execute(
            "UPDATE checkpoint_linhas SET status = ?, extra = ? "
            "WHERE checkpoint_id = ? AND idx = ?",
            (status, json.dumps(dados, ensure_ascii=False), cid, index))
    else:
        con.execute(
            "UPDATE checkpoint_linhas SET status = ?, numero_filho = ?, extra = ? "
            "WHERE checkpoint_id = ? AND idx = ?",
            (status, numero_filho, json.dumps(dados, ensure_ascii=False),
             cid, index))
    return True


def marcar_salvo(numero_chamado: str, index: int, numero_filho: str = "") -> None:
    """Marca linha como salva (chamado criado, BC pendente). Salva o numero do filho."""
    with db.transacao() as con:
        cid = _rodada(con, numero_chamado)
        if cid is None:
            return
        _atualizar_linha(con, cid, index, STATUS_SALVO,
                         numero_filho=numero_filho, salvo_em=_agora())
        con.execute("UPDATE checkpoints SET atualizado_em = ? WHERE id = ?",
                    (_agora(), cid))


def numero_filho(numero_chamado: str, index: int) -> str:
    """Retorna o numero do chamado filho para uma linha salva."""
    for l in status_linhas(numero_chamado):
        if l["index"] == index:
            return l.get("numero_filho", "")
    return ""


def marcar_concluido_linha(numero_chamado: str, index: int, **extra) -> None:
    """Marca linha como concluida (chamado + BC adicionados).

    `**extra` grava campos adicionais na linha (ex.: `numero=`, `usuario=`) —
    para fluxos de uma fase so (sem SALVO intermediario, ex. Requisicao de
    Servico) que precisam reconstruir a tabela de resultados inteira ao
    retomar um lote, nao so saber "concluida sim/nao".
    """
    with db.transacao() as con:
        cid = _rodada(con, numero_chamado)
        if cid is None:
            return
        _atualizar_linha(con, cid, index, STATUS_CONCLUIDO,
                         concluido_em=_agora(), **extra)
        falta = con.execute(
            "SELECT 1 FROM checkpoint_linhas WHERE checkpoint_id = ? AND status != ?",
            (cid, STATUS_CONCLUIDO)).fetchone()
        con.execute(
            "UPDATE checkpoints SET concluido = ?, atualizado_em = ? WHERE id = ?",
            (int(falta is None), _agora(), cid))


def carregar(numero_chamado: str) -> dict | None:
    return _carregar_dados(numero_chamado)


def _path_legado(numero_chamado: str):
    """Onde o JSON do formato antigo estaria (sem criar pasta nenhuma)."""
    nome = numero_chamado.strip().replace("/", "_").replace("\\", "_")
    return (_CHECKPOINTS_DIR / nome / f"{nome}.json",
            _CHECKPOINTS_DIR / f"{nome}.json")


def esta_corrompido(numero_chamado: str) -> bool:
    """O checkpoint existe mas nao da para ler? (NAO confundir com "nao existe".)

    `_carregar_dados` devolve None nos DOIS casos, e quem chama nao consegue
    distinguir "chamado novo" de "checkpoint quebrado". Como o fluxo inicializa
    tudo como pendente quando conclui "chamado novo", um checkpoint ilegivel o
    fazia RECRIAR todos os filhos ja criados — em silencio.

    No banco nao existe "meio gravado". O que sobra e o JSON do formato
    antigo que o db.py NAO conseguiu importar (ilegivel) — ou que um processo
    ainda com codigo antigo gravou depois da importacao. Nos dois casos a
    resposta segura e a mesma: existe algo nao lido para esta chave, entao
    nao e "chamado novo". Por isso quem for inicializar pergunta isto ANTES.
    """
    if _carregar_dados(numero_chamado) is not None:
        return False
    return any(p.exists() for p in _path_legado(numero_chamado))


def existe_pendente(numero_chamado: str) -> bool:
    """Verifica se existe checkpoint com linhas nao concluidas para esse chamado."""
    dados = _carregar_dados(numero_chamado)
    if not dados:
        return False
    if dados.get("concluido", False):
        return False
    return any(
        l["status"] in [STATUS_PENDENTE, STATUS_SALVO]
        for l in dados.get("linhas", [])
    )


def foi_concluido(numero_chamado: str) -> bool:
    """Retorna True se o checkpoint existe e todas as linhas foram concluidas."""
    dados = _carregar_dados(numero_chamado)
    if not dados:
        return False
    return dados.get("concluido", False)


def status_linhas(numero_chamado: str) -> list[dict]:
    """Retorna a lista de status de cada linha."""
    dados = _carregar_dados(numero_chamado)
    if not dados:
        return []
    return dados.get("linhas", [])


def status_linha(numero_chamado: str, index: int) -> str:
    """Retorna o status de uma linha especifica."""
    for l in status_linhas(numero_chamado):
        if l["index"] == index:
            return l["status"]
    return STATUS_PENDENTE


def resumo(numero_chamado: str) -> str:
    """Retorna string resumindo o progresso."""
    dados = _carregar_dados(numero_chamado)
    if not dados:
        return ""
    linhas     = dados.get("linhas", [])
    total      = len(linhas)
    concluidos = sum(1 for l in linhas if l["status"] == STATUS_CONCLUIDO)
    salvos     = sum(1 for l in linhas if l["status"] == STATUS_SALVO)
    data       = dados.get("atualizado_em", "")
    partes = [f"{concluidos} de {total} concluidas"]
    if salvos:
        partes.append(f"{salvos} salvas sem BC")
    return f"{' | '.join(partes)} — {data}"


def limpar(numero_chamado: str) -> None:
    """Remove TODAS as rodadas da chave, historico incluido (as linhas vao
    junto pelo ON DELETE CASCADE)."""
    with db.transacao() as con:
        con.execute("DELETE FROM checkpoints WHERE chave = ?", (numero_chamado,))


def _linha_dict(r) -> dict:
    linha = {"index": r["idx"], "status": r["status"]}
    extra = json.loads(r["extra"])
    if r["numero_filho"] or "salvo_em" in extra:
        linha["numero_filho"] = r["numero_filho"]
    if r["referencia"]:
        linha["referencia"] = r["referencia"]
    linha.update(extra)
    return linha


def _carregar_dados(numero_chamado: str) -> dict | None:
    """Monta o mesmo dict do antigo JSON (da rodada vigente): numero_chamado,
    total, criado_em, atualizado_em, concluido e linhas [{index, status,
    numero_filho?, ...}]."""
    with db.leitura() as con:
        cid = _rodada(con, numero_chamado)
        if cid is None:
            return None
        cab = con.execute("SELECT * FROM checkpoints WHERE id = ?", (cid,)).fetchone()
        rows = con.execute(
            "SELECT * FROM checkpoint_linhas WHERE checkpoint_id = ? ORDER BY idx",
            (cid,)).fetchall()
    return {
        "numero_chamado": cab["chave"],
        "total":          cab["total"],
        "criado_em":      cab["criado_em"],
        "atualizado_em":  cab["atualizado_em"],
        "concluido":      bool(cab["concluido"]),
        "linhas":         [_linha_dict(r) for r in rows],
    }


# --------------------------------------------------------------------------- #
# Historico (pagina "Meus fluxos")
# --------------------------------------------------------------------------- #

def historico(matricula: str, limite: int = 200) -> list[dict]:
    """Rodadas da matricula, da mais recente para a mais antiga, cada uma com
    as suas linhas. `vigente` diz se e a rodada que um "Retomar" continuaria
    (False = substituida por um "Do zero" posterior da mesma chave)."""
    with db.leitura() as con:
        cabs = con.execute(
            "SELECT c.*, (c.id = (SELECT MAX(id) FROM checkpoints WHERE chave = c.chave)) "
            "AS vigente FROM checkpoints c WHERE c.matricula = ? "
            "ORDER BY c.id DESC LIMIT ?", (matricula, limite)).fetchall()
        ids = [c["id"] for c in cabs]
        rows = con.execute(
            f"SELECT * FROM checkpoint_linhas WHERE checkpoint_id IN "
            f"({','.join('?' * len(ids))}) ORDER BY checkpoint_id, idx",
            ids).fetchall() if ids else []
    por_rodada: dict[int, list[dict]] = {}
    for r in rows:
        por_rodada.setdefault(r["checkpoint_id"], []).append(_linha_dict(r))
    return [
        {
            "id":            c["id"],
            "chave":         c["chave"],
            "fluxo":         c["fluxo"],
            "origem":        c["origem"],
            "total":         c["total"],
            "criado_em":     c["criado_em"],
            "atualizado_em": c["atualizado_em"],
            "concluido":     bool(c["concluido"]),
            "vigente":       bool(c["vigente"]),
            "linhas":        por_rodada.get(c["id"], []),
        }
        for c in cabs
    ]
