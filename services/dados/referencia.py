"""
services/dados/referencia.py — Dados de REFERÊNCIA do CATI para o Assistente
completar o que o técnico não diz (21/10).

Tabelas em services/agente/conhecimento/referencia/ (versionadas; a
atualização leva a todos). Eram CSVs em data/referencia/ até 27/10: viraram
tabelas .md para todo dado escrito por gente ficar num formato só (o SQLite
é só do que o app grava). A pasta é lida SÓ pelo código — não vai para a IA
(services/agente/conhecimento.py).
  - filas.md     (nome, codigo, ans): os 205 Departamentos de Serviço do
                 Assyst, extraídos da busca '*' da Atribuição Interna
                 (teste_extrair_filas.py). Para atualizar: rodar de novo.
  - edificios.md (secao, grupo, edificio, qtd): em que edifício os chamados
                 de cada Seção foram atendidos (teste_extrair_edificios.py e
                 teste_ampliar_edificios.py). Usado na triagem
                 (services/agente/triagem.py).
  - tecnicos.md  (nome, fila): UMA LINHA POR PAR — o mesmo técnico pode estar
                 em várias filas (ex.: FCB e Remoto, conforme o local). Nome
                 exatamente como no Assyst. Editável à mão.

Formato: texto livre no começo (explicação para quem edita) e UMA tabela
markdown; a 1ª linha da tabela são os nomes das colunas. `|` dentro de um
valor vai escrito `\\|`.

Resolver = transformar o que o técnico disse ("iguatu", "Gabriel") no nome
EXATO do Assyst, ou dizer por que não deu (ambíguo / não achou). Nada aqui
chuta: ambíguo volta as opções para o agente perguntar.
"""

import dataclasses
import os
import re
import unicodedata
from pathlib import Path

PASTA = Path(__file__).resolve().parents[1] / "agente" / "conhecimento" / "referencia"
_cache: dict[str, tuple[float, list[dict]]] = {}

_DIVISOR = re.compile(r"^\|?[\s:|-]+$")          # |---|:--|
_PIPE = re.compile(r"(?<!\\)\|")                # | que não é \|


def _celulas(linha: str) -> list[str]:
    linha = linha.strip().removeprefix("|")
    if linha.endswith("|") and not linha.endswith("\\|"):
        linha = linha[:-1]
    return [c.strip().replace("\\|", "|") for c in _PIPE.split(linha)]


def _tabela(texto: str) -> list[dict]:
    """A (primeira) tabela markdown do texto como lista de dicts."""
    tabela = [l for l in texto.splitlines() if l.strip().startswith("|")]
    if not tabela:
        return []
    colunas = [c.lower() for c in _celulas(tabela[0])]
    corpo = tabela[1:]
    if corpo and _DIVISOR.match(corpo[0].strip()):
        corpo = corpo[1:]
    saida = []
    for l in corpo:
        valores = _celulas(l)
        saida.append({c: (valores[i] if i < len(valores) else "")
                      for i, c in enumerate(colunas)})
    return saida


def _ler(nome: str, chave: str = "nome") -> list[dict]:
    """Linhas da tabela, relidas só quando o arquivo muda (a atualização
    troca). Linha sem a coluna `chave` preenchida é descartada."""
    arq = PASTA / nome
    try:
        mtime = arq.stat().st_mtime
    except OSError:
        return []
    if nome not in _cache or _cache[nome][0] != mtime:
        linhas = _tabela(arq.read_text(encoding="utf-8"))
        _cache[nome] = (mtime, [l for l in linhas if l.get(chave)])
    return _cache[nome][1]


def gravar(nome: str, colunas: list[str], linhas: list[list]) -> Path:
    """Regrava a tabela de `nome` (scripts de extração), mantendo o texto
    explicativo de antes dela. Escrita atômica (.tmp + replace)."""
    arq = PASTA / nome
    try:
        antes = arq.read_text(encoding="utf-8")
        intro = antes.split("\n|", 1)[0].rstrip()
    except OSError:
        intro = f"# {arq.stem}"

    def _linha(valores) -> str:
        return "| " + " | ".join(str(v).replace("|", "\\|") for v in valores) + " |"

    corpo = [_linha(colunas), "|" + "---|" * len(colunas), *map(_linha, linhas)]
    PASTA.mkdir(parents=True, exist_ok=True)
    tmp = arq.with_suffix(".tmp")
    tmp.write_text(intro + "\n\n" + "\n".join(corpo) + "\n", encoding="utf-8")
    os.replace(tmp, arq)
    return arq


def _chave(s: str) -> str:
    t = unicodedata.normalize("NFD", (s or "").lower())
    return " ".join("".join(c for c in t if unicodedata.category(c) != "Mn").split())


@dataclasses.dataclass
class Achado:
    valor: str = ""                                   # nome exato, se UM só
    opcoes: list[str] = dataclasses.field(default_factory=list)  # se ambíguo

    @property
    def ok(self) -> bool:
        return bool(self.valor)


def filas() -> list[str]:
    return [l["nome"] for l in _ler("filas.md")]


def resolver_fila(texto: str) -> Achado:
    """'iguatu' -> '2N CATI Polo Iguatu'; 'tj' -> '2N CATI TJ'.

    Ordem: nome ou código exato; com '2N CATI ' na frente (o técnico fala só
    o fim); um único nome que contenha o texto; senão, ambíguo/não achou."""
    k = _chave(texto)
    if not k:
        return Achado()
    linhas = _ler("filas.md")
    for alvo in (k, _chave("2N CATI " + texto)):
        for l in linhas:
            if alvo in (_chave(l["nome"]), _chave(l["codigo"])):
                return Achado(l["nome"])
    contem = [l["nome"] for l in linhas if k in _chave(l["nome"])]
    # Preferência para as do 2N CATI: "fcb" é a 2N CATI FCB, não as 2N CIAT FCB.
    cati = [n for n in contem if n.startswith("2N CATI")]
    for grupo in (cati, contem):
        if len(grupo) == 1:
            return Achado(grupo[0])
    return Achado(opcoes=(cati or contem)[:10])


def tecnicos() -> list[str]:
    return sorted({l["nome"] for l in _ler("tecnicos.md")})


def filas_do_tecnico(nome: str) -> list[str]:
    return [l["fila"] for l in _ler("tecnicos.md") if l["nome"] == nome and l.get("fila")]


def resolver_tecnico(texto: str) -> Achado:
    """'Gabriel' -> ambíguo (dois Gabriel); 'Gabriel Elias' -> o nome inteiro.
    Cada palavra dita tem que ser o COMEÇO de uma palavra do nome."""
    palavras = _chave(texto).split()
    if not palavras:
        return Achado()
    nomes = sorted({l["nome"] for l in _ler("tecnicos.md")})
    exato = [n for n in nomes if _chave(n) == " ".join(palavras)]
    if exato:
        return Achado(exato[0])
    batem = [n for n in nomes
             if all(any(p.startswith(w) for p in _chave(n).split()) for w in palavras)]
    if len(batem) == 1:
        return Achado(batem[0])
    return Achado(opcoes=batem[:10])


def edificios() -> list[dict]:
    """Linhas do edificios.md: secao, grupo, edificio, qtd (texto)."""
    return _ler("edificios.md", chave="secao")
