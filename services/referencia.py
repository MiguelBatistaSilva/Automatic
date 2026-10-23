"""
services/referencia.py — Dados de REFERÊNCIA do CATI para o Assistente
completar o que o técnico não diz (21/10).

Arquivos em data/referencia/ (versionados; a atualização leva a todos — mesmo
motivo que tirou os tipos de solicitação do SQLite em 01/10):
  - filas.csv    (nome,codigo,ans): os 205 Departamentos de Serviço do Assyst,
                 extraídos da busca '*' da Atribuição Interna
                 (teste_extrair_filas.py). Para atualizar: rodar de novo.
  - edificios.csv (secao,grupo,edificio,qtd): em que edifício os chamados de
                 cada Seção foram atendidos (teste_extrair_edificios.py e
                 teste_ampliar_edificios.py). Usado na triagem
                 (services/triagem.py).
  - tecnicos.csv (nome,fila): UMA LINHA POR PAR — o mesmo técnico pode estar
                 em várias filas (ex.: FCB e Remoto, conforme o local). Nome
                 exatamente como no Assyst. Editável à mão.

Resolver = transformar o que o técnico disse ("iguatu", "Gabriel") no nome
EXATO do Assyst, ou dizer por que não deu (ambíguo / não achou). Nada aqui
chuta: ambíguo volta as opções para o agente perguntar.
"""

import csv
import dataclasses
import unicodedata
from pathlib import Path

from services.paths import DATA_DIR

PASTA = Path(DATA_DIR) / "referencia"
_cache: dict[str, tuple[float, list[dict]]] = {}


def _ler(nome: str, chave: str = "nome") -> list[dict]:
    """Linhas do CSV, relidas só quando o arquivo muda (a atualização troca).
    Linha sem a coluna `chave` preenchida é descartada."""
    arq = PASTA / nome
    try:
        mtime = arq.stat().st_mtime
    except OSError:
        return []
    if nome not in _cache or _cache[nome][0] != mtime:
        with open(arq, encoding="utf-8", newline="") as f:
            linhas = [{k: (v or "").strip() for k, v in l.items()} for l in csv.DictReader(f)]
        _cache[nome] = (mtime, [l for l in linhas if l.get(chave)])
    return _cache[nome][1]


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
    return [l["nome"] for l in _ler("filas.csv")]


def resolver_fila(texto: str) -> Achado:
    """'iguatu' -> '2N CATI Polo Iguatu'; 'tj' -> '2N CATI TJ'.

    Ordem: nome ou código exato; com '2N CATI ' na frente (o técnico fala só
    o fim); um único nome que contenha o texto; senão, ambíguo/não achou."""
    k = _chave(texto)
    if not k:
        return Achado()
    linhas = _ler("filas.csv")
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
    return sorted({l["nome"] for l in _ler("tecnicos.csv")})


def filas_do_tecnico(nome: str) -> list[str]:
    return [l["fila"] for l in _ler("tecnicos.csv") if l["nome"] == nome and l.get("fila")]


def resolver_tecnico(texto: str) -> Achado:
    """'Gabriel' -> ambíguo (dois Gabriel); 'Gabriel Elias' -> o nome inteiro.
    Cada palavra dita tem que ser o COMEÇO de uma palavra do nome."""
    palavras = _chave(texto).split()
    if not palavras:
        return Achado()
    nomes = sorted({l["nome"] for l in _ler("tecnicos.csv")})
    exato = [n for n in nomes if _chave(n) == " ".join(palavras)]
    if exato:
        return Achado(exato[0])
    batem = [n for n in nomes
             if all(any(p.startswith(w) for p in _chave(n).split()) for w in palavras)]
    if len(batem) == 1:
        return Achado(batem[0])
    return Achado(opcoes=batem[:10])


def edificios() -> list[dict]:
    """Linhas do edificios.csv: secao, grupo, edificio, qtd (texto)."""
    return _ler("edificios.csv", chave="secao")
