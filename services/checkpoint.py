"""
services/checkpoint.py — Gerencia o progresso linha a linha com 3 estados:
  pendente  → ainda nao processada
  salvo     → chamado criado mas BC ainda nao adicionada
  concluido → chamado criado + BC adicionada

Cada chamado tem seu proprio arquivo JSON em data/checkpoints/{numero}.json
"""
import json
import os
from datetime import datetime
from pathlib import Path

from services.paths import CHECKPOINTS_DIR as _CHECKPOINTS_DIR

STATUS_PENDENTE  = "pendente"
STATUS_SALVO     = "salvo"
STATUS_CONCLUIDO = "concluido"


def _agora() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def _path(numero_chamado: str) -> Path:
    """Retorna o caminho do arquivo JSON para um chamado especifico."""
    _CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
    # Sanitiza o numero para uso como nome de arquivo
    nome = numero_chamado.strip().replace("/", "_").replace("\\", "_")
    return _CHECKPOINTS_DIR / f"{nome}.json"


def inicializar(numero_chamado: str, total: int) -> None:
    """Cria um checkpoint novo com todas as linhas como pendente."""
    dados = {
        "numero_chamado": numero_chamado,
        "total":          total,
        "criado_em":      _agora(),
        "atualizado_em":  _agora(),
        "concluido":      False,
        "linhas": [
            {"index": i, "status": STATUS_PENDENTE}
            for i in range(total)
        ],
    }
    _salvar_dados(numero_chamado, dados)


def marcar_salvo(numero_chamado: str, index: int, numero_filho: str = "") -> None:
    """Marca linha como salva (chamado criado, BC pendente). Salva o numero do filho."""
    dados = _carregar_dados(numero_chamado)
    if not dados:
        return
    for linha in dados["linhas"]:
        if linha["index"] == index:
            linha["status"]       = STATUS_SALVO
            linha["salvo_em"]     = _agora()
            linha["numero_filho"] = numero_filho
            break
    dados["atualizado_em"] = _agora()
    _salvar_dados(numero_chamado, dados)


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
    dados = _carregar_dados(numero_chamado)
    if not dados:
        return
    for linha in dados["linhas"]:
        if linha["index"] == index:
            linha["status"]       = STATUS_CONCLUIDO
            linha["concluido_em"] = _agora()
            linha.update(extra)
            break
    todas = all(l["status"] == STATUS_CONCLUIDO for l in dados["linhas"])
    dados["concluido"]     = todas
    dados["atualizado_em"] = _agora()
    _salvar_dados(numero_chamado, dados)


def carregar(numero_chamado: str) -> dict | None:
    return _carregar_dados(numero_chamado)


def esta_corrompido(numero_chamado: str) -> bool:
    """O arquivo existe mas nao da para ler? (NAO confundir com "nao existe".)

    `_carregar_dados` devolve None nos DOIS casos, e quem chama nao consegue
    distinguir "chamado novo" de "checkpoint quebrado". Como o fluxo inicializa
    tudo como pendente quando conclui "chamado novo", um arquivo ilegivel o fazia
    RECRIAR todos os filhos ja criados — em silencio, com o log dizendo apenas
    "Inicializando checkpoint...", que e a mesma frase de uma execucao legitima
    do zero.

    Por isso quem for decidir inicializar precisa perguntar isto ANTES.
    """
    p = _path(numero_chamado)
    if not p.exists():
        return False
    try:
        with open(p, "r", encoding="utf-8") as f:
            json.load(f)
        return False
    except Exception:
        return True


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
    """Remove o arquivo de checkpoint de um chamado especifico."""
    p = _path(numero_chamado)
    if p.exists():
        p.unlink()


def _carregar_dados(numero_chamado: str) -> dict | None:
    p = _path(numero_chamado)
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _salvar_dados(numero_chamado: str, dados: dict) -> None:
    """Grava o checkpoint de forma ATOMICA (temporario + os.replace).

    O `open(p, "w")` ZERA o arquivo antes de escrever: morrer nesse instante
    (backend do Reflex reiniciando, maquina desligando) deixava um JSON pela
    metade. `_carregar_dados` nao le esse arquivo, devolve None, e o fluxo
    concluia "chamado novo" e recriava TODOS os filhos ja criados.

    Com a troca atomica o arquivo bom so deixa de existir quando o novo ja esta
    inteiro no disco. O pior caso passa a ser "perdi a ultima linha marcada" —
    que a retomada resolve — em vez de "corrompi o checkpoint".

    Sem `fsync` de proposito: ele protegeria contra queda de energia, mas custa
    em TODA linha marcada, e a morte real aqui e o processo sendo derrubado —
    para essa, o `os.replace` sozinho basta.
    """
    p = _path(numero_chamado)
    p.parent.mkdir(parents=True, exist_ok=True)
    # `p.name + ".tmp.json"` e nao `with_suffix`: o numero do chamado pode conter
    # ponto, e `with_suffix` comeria o trecho depois dele. Termina em ".json" (e
    # nao ".tmp") de proposito: em desenvolvimento o `reflex run` observa a pasta
    # do projeto INTEIRA para hot-reload e ignora extensoes conhecidas (json,
    # txt, log...) mas NAO ignora ".tmp" — um arquivo terminado em ".tmp" aqui
    # disparava o reload do backend a cada linha marcada, matando a thread do
    # worker no meio do fluxo (era exatamente o que travava o Desmembramento
    # logo apos "Inicializando checkpoint...", sem excecao nenhuma no log).
    tmp = p.parent / (p.name + ".tmp.json")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)  # atomico no Windows (mesmo volume)