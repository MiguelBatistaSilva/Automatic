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


def _existe(con, numero_chamado: str) -> bool:
    return con.execute("SELECT 1 FROM checkpoints WHERE chave = ?",
                       (numero_chamado,)).fetchone() is not None


def inicializar(numero_chamado: str, total: int) -> None:
    """Cria um checkpoint novo com todas as linhas como pendente (substitui
    o que houver para a chave — e o "Do zero" dos dialogos)."""
    agora = _agora()
    with db.transacao() as con:
        con.execute("DELETE FROM checkpoint_linhas WHERE chave = ?", (numero_chamado,))
        con.execute("DELETE FROM checkpoints WHERE chave = ?", (numero_chamado,))
        con.execute("INSERT INTO checkpoints VALUES (?, ?, ?, ?, 0)",
                    (numero_chamado, total, agora, agora))
        con.executemany(
            "INSERT INTO checkpoint_linhas (chave, idx, status) VALUES (?, ?, ?)",
            [(numero_chamado, i, STATUS_PENDENTE) for i in range(total)])


def _atualizar_linha(con, numero_chamado, index, status, numero_filho=None,
                     **extra) -> bool:
    r = con.execute(
        "SELECT extra FROM checkpoint_linhas WHERE chave = ? AND idx = ?",
        (numero_chamado, index)).fetchone()
    if r is None:
        return False
    dados = json.loads(r["extra"])
    dados.update(extra)
    if numero_filho is None:
        con.execute(
            "UPDATE checkpoint_linhas SET status = ?, extra = ? "
            "WHERE chave = ? AND idx = ?",
            (status, json.dumps(dados, ensure_ascii=False), numero_chamado, index))
    else:
        con.execute(
            "UPDATE checkpoint_linhas SET status = ?, numero_filho = ?, extra = ? "
            "WHERE chave = ? AND idx = ?",
            (status, numero_filho, json.dumps(dados, ensure_ascii=False),
             numero_chamado, index))
    return True


def marcar_salvo(numero_chamado: str, index: int, numero_filho: str = "") -> None:
    """Marca linha como salva (chamado criado, BC pendente). Salva o numero do filho."""
    with db.transacao() as con:
        if not _existe(con, numero_chamado):
            return
        _atualizar_linha(con, numero_chamado, index, STATUS_SALVO,
                         numero_filho=numero_filho, salvo_em=_agora())
        con.execute("UPDATE checkpoints SET atualizado_em = ? WHERE chave = ?",
                    (_agora(), numero_chamado))


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
        if not _existe(con, numero_chamado):
            return
        _atualizar_linha(con, numero_chamado, index, STATUS_CONCLUIDO,
                         concluido_em=_agora(), **extra)
        falta = con.execute(
            "SELECT 1 FROM checkpoint_linhas WHERE chave = ? AND status != ?",
            (numero_chamado, STATUS_CONCLUIDO)).fetchone()
        con.execute(
            "UPDATE checkpoints SET concluido = ?, atualizado_em = ? WHERE chave = ?",
            (int(falta is None), _agora(), numero_chamado))


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
    """Remove o checkpoint de um chamado especifico."""
    with db.transacao() as con:
        con.execute("DELETE FROM checkpoint_linhas WHERE chave = ?", (numero_chamado,))
        con.execute("DELETE FROM checkpoints WHERE chave = ?", (numero_chamado,))


def _carregar_dados(numero_chamado: str) -> dict | None:
    """Monta o mesmo dict do antigo JSON: numero_chamado, total, criado_em,
    atualizado_em, concluido e linhas [{index, status, numero_filho?, ...}]."""
    with db.leitura() as con:
        cab = con.execute("SELECT * FROM checkpoints WHERE chave = ?",
                          (numero_chamado,)).fetchone()
        if cab is None:
            return None
        rows = con.execute(
            "SELECT * FROM checkpoint_linhas WHERE chave = ? ORDER BY idx",
            (numero_chamado,)).fetchall()
    linhas = []
    for r in rows:
        linha = {"index": r["idx"], "status": r["status"]}
        extra = json.loads(r["extra"])
        if r["numero_filho"] or "salvo_em" in extra:
            linha["numero_filho"] = r["numero_filho"]
        linha.update(extra)
        linhas.append(linha)
    return {
        "numero_chamado": cab["chave"],
        "total":          cab["total"],
        "criado_em":      cab["criado_em"],
        "atualizado_em":  cab["atualizado_em"],
        "concluido":      bool(cab["concluido"]),
        "linhas":         linhas,
    }
