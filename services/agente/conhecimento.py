"""
services/agente/conhecimento.py — Lê a base de conhecimento do Assistente.

A base são os arquivos `.md` de services/agente/conhecimento/ (ver o README
de lá). Fonte ÚNICA do que o Assistente sabe sobre o CATI/Assyst desde
2026-10-01 — antes estava espalhado no prompt, nas descrições das
ferramentas e numa tabela do banco (Configurações -> Tipos de Solicitação,
removida).

  texto()  -> todos os arquivos juntos, para as instruções da IA;
  tipos()  -> os tipos de solicitação, lidos pelo CÓDIGO (Requisição por tombo).

Lido a cada pedido (são poucos KB): editar um arquivo vale na hora, sem
reiniciar o app.
"""

import dataclasses
import re
from pathlib import Path

PASTA = Path(__file__).parent / "conhecimento"
_ARQ_TIPOS = PASTA / "tipos_solicitacao.md"


@dataclasses.dataclass
class Tipo:
    nome: str
    pedidos: str
    item: str
    categoria: str
    resumo: str
    descricao: str


def _arquivos() -> list[Path]:
    return sorted(p for p in PASTA.glob("*.md") if p.name.lower() != "readme.md")


def texto() -> str:
    """A base inteira, para as instruções do modelo."""
    partes = []
    for p in _arquivos():
        try:
            partes.append(p.read_text(encoding="utf-8").strip())
        except OSError:
            continue
    return "\n\n".join(partes)


def tipos() -> list[Tipo]:
    """Os tipos de solicitação de tipos_solicitacao.md.

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
