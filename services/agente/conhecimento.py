"""
services/agente/conhecimento.py — Lê a base de conhecimento do Assistente.

A base são os arquivos `.md` de services/agente/conhecimento/ (ver o README
de lá). Fonte ÚNICA do que o Assistente sabe sobre o CATI/Assyst desde
2026-10-01.

ORGANIZADA POR DOMÍNIO (07/10): cada subpasta é um domínio (chamados/,
requisicao/, filas/ ...) — o mesmo nome do `dominio` das ferramentas e do
roteador (services/agente/roteador.py). Arquivo na raiz vale para todos.

  texto(dominios) -> raiz + os domínios do pedido, para as instruções da IA;
  indice()        -> a lista de TODOS os assuntos (vai nas instruções, curta);
  ler(assunto)    -> um assunto inteiro (ferramenta consultar_conhecimento);
  tipos()         -> os tipos de solicitação, lidos pelo CÓDIGO.
  despachos()     -> os modelos de despacho, lidos SÓ pelo código (26/10).

A subpasta referencia/ (técnicos, filas, edifícios) também é SÓ do código:
quem lê é services/dados/referencia.py.

Lido a cada pedido (são poucos KB): editar um arquivo vale na hora, sem
reiniciar o app.
"""

import dataclasses
import re
from pathlib import Path

PASTA = Path(__file__).parent / "conhecimento"
_ARQ_TIPOS = PASTA / "requisicao" / "tipos_solicitacao.md"
# Dado que só o CÓDIGO lê: fica fora das instruções, do índice e do
# consultar_conhecimento (os modelos de despacho são ~3.000 tokens, que iriam
# em todo pedido de chamados; a IA só precisa dos nomes — ver despachos()).
_ARQ_DESPACHOS = PASTA / "chamados" / "despachos.md"
_SO_CODIGO = {_ARQ_DESPACHOS}
# Pasta inteira só do código: as tabelas de técnicos, filas e edifícios
# (services/dados/referencia.py; ~500 linhas — nunca em toda ida à IA).
_PASTAS_SO_CODIGO = {"referencia"}


@dataclasses.dataclass
class Tipo:
    nome: str
    pedidos: str
    item: str
    categoria: str
    resumo: str
    descricao: str


@dataclasses.dataclass
class ModeloDespacho:
    nome: str
    tipo: str
    pedidos: str
    defeito: str
    testes: list[str]


def _arquivos(dominios: "set[str] | None" = None) -> list[Path]:
    """Raiz sempre; subpastas só as de `dominios` (None = todas)."""
    saida = []
    for p in sorted(PASTA.rglob("*.md")):
        rel = p.relative_to(PASTA)
        if (p.name.lower() == "readme.md" or p in _SO_CODIGO
                or rel.parts[0] in _PASTAS_SO_CODIGO):
            continue
        if len(rel.parts) == 1 or dominios is None or rel.parts[0] in dominios:
            saida.append(p)
    return saida


def _ler(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def texto(dominios: "set[str] | None" = None) -> str:
    """A base dos `dominios` (None = inteira), para as instruções do modelo."""
    return "\n\n".join(t for t in map(_ler, _arquivos(dominios)) if t)


def _chave(p: Path) -> str:
    return p.relative_to(PASTA).with_suffix("").as_posix()  # "chamados/sla"


def _titulo(p: Path) -> str:
    m = re.search(r"^#\s+(.+)$", _ler(p), flags=re.M)
    return m[1].strip() if m else p.stem


def indice() -> str:
    """Uma linha por assunto: '- chamados/sla — SLA'."""
    return "\n".join(f"- {_chave(p)} — {_titulo(p)}" for p in _arquivos())


def ler(assunto: str) -> str:
    """O assunto pela chave ('filas/filas') ou por palavras da chave/título
    ('filas', 'sla'). Mais de um casando = todos juntos (são curtos)."""
    alvo = (assunto or "").strip().lower().removesuffix(".md")
    todos = _arquivos()
    achados = [p for p in todos if _chave(p).lower() == alvo]
    if not achados:
        palavras = [w for w in re.split(r"[\s/_-]+", alvo) if len(w) > 2]
        achados = [p for p in todos if palavras and all(
            w in f"{_chave(p)} {_titulo(p)}".lower() for w in palavras)]
    if not achados:
        return f"Assunto '{assunto}' não encontrado. Assuntos:\n{indice()}"
    return "\n\n".join(_ler(p) for p in achados)


def tipos() -> list[Tipo]:
    """Os tipos de solicitação de requisicao/tipos_solicitacao.md.

    Bloco = título `## Nome` + linhas `- campo: valor`. Bloco sem item ou
    sem descrição é ignorado (não derruba os outros).
    """
    try:
        conteudo = _ARQ_TIPOS.read_text(encoding="utf-8")
    except OSError:
        return []
    saida = []
    for bloco in re.split(r"^##\s+", conteudo, flags=re.M)[1:]:
        linhas = bloco.strip().splitlines()
        campos = {}
        for l in linhas[1:]:
            m = re.match(r"\s*-\s*(\w+)\s*:\s*(.*)$", l)
            if m:
                campos[m[1].lower()] = m[2].strip()
        if campos.get("item") and campos.get("descricao"):
            saida.append(Tipo(
                nome=linhas[0].strip(),
                pedidos=campos.get("pedidos", ""),
                item=campos["item"],
                categoria=campos.get("categoria") or "Configuração",
                resumo=campos.get("resumo") or "Requisição de Serviço",
                descricao=campos["descricao"],
            ))
    return saida


def despachos() -> list[ModeloDespacho]:
    """Os modelos de chamados/despachos.md (formato descrito lá).

    Bloco = título `## Nome` + `- campo: valor` + `- testes:` com um teste
    por linha (`  - ...`). Bloco sem tipo, defeito ou testes é ignorado.
    """
    try:
        conteudo = _ARQ_DESPACHOS.read_text(encoding="utf-8")
    except OSError:
        return []
    saida = []
    for bloco in re.split(r"^##\s+", conteudo, flags=re.M)[1:]:
        linhas = bloco.strip().splitlines()
        campos, testes = {}, []
        for l in linhas[1:]:
            if re.match(r"\s{2,}-\s", l):          # item da lista de testes
                testes.append(l.strip()[1:].strip().rstrip(";.").strip())
                continue
            m = re.match(r"-\s*(\w+)\s*:\s*(.*)$", l)
            if m:
                campos[m[1].lower()] = m[2].strip()
        if campos.get("tipo") and campos.get("defeito") and testes:
            saida.append(ModeloDespacho(
                nome=linhas[0].strip(), tipo=campos["tipo"],
                pedidos=campos.get("pedidos", ""),
                defeito=campos["defeito"].rstrip(";.").strip(), testes=testes))
    return saida
