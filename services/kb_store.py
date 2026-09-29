"""
services/kb_store.py — Bases de Conhecimento cadastradas nesta maquina.

Moram no banco (services/db.py, tabela kb_bases) desde 2026-09-28. Antes era
data/kb_configs.json — versionado no git, e por isso o updater o sobrescrevia
a cada atualizacao, apagando as bases que cada tecnico cadastrou. O JSON e
importado uma vez so; depois disso o updater pode trazer o que quiser.
"""
from services import db


def carregar() -> list[dict]:
    return [{"keyword": r["keyword"], "nome_artigo": r["nome_artigo"]}
            for r in db.consultar(
                "SELECT keyword, nome_artigo FROM kb_bases ORDER BY id")]


def salvar(entries: list[dict]) -> None:
    """Substitui TODAS as bases pela lista recebida (mesma semantica do JSON)."""
    with db.transacao() as con:
        con.execute("DELETE FROM kb_bases")
        for e in entries:
            con.execute(
                "INSERT INTO kb_bases (keyword, nome_artigo) VALUES (?, ?)",
                (e["keyword"], e["nome_artigo"]))
