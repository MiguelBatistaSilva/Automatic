"""
relatorio_agente.py — Lê o registro dos pedidos ao Assistente (08/10).

Os pedidos ficam no banco DESTA máquina (services/agente/registro.py), por
30 dias. Para analisar os da equipe: cada técnico roda com --csv e manda o
arquivo (os pedidos citam nomes e chamados — tratar como dado interno).

Uso:
    python relatorio_agente.py                 resumo dos últimos 30 dias
    python relatorio_agente.py --dias 7        só a última semana
    python relatorio_agente.py --ultimos 30    lista os 30 pedidos mais recentes
    python relatorio_agente.py --csv pedidos.csv   exporta tudo para planilha

O que olhar primeiro: a seção "PARA INVESTIGAR" (a IA deu erro, a execução
falhou, ou o roteador não achou a ferramenta e precisou mandar todas). Frase
que caiu no domínio errado vira caso do eval_roteador.py.
"""

import argparse
import csv
import datetime
import json
import os
import statistics
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services import db


def _carregar(dias: int) -> list[dict]:
    desde = (datetime.datetime.now() - datetime.timedelta(days=dias)).isoformat(timespec="seconds")
    linhas = db.consultar("SELECT * FROM agente_pedidos WHERE quando >= ? ORDER BY quando", (desde,))
    saida = []
    for l in linhas:
        d = dict(l)
        d["chamadas"] = json.loads(d["chamadas"] or "[]")
        d["resultado"] = json.loads(d["resultado"] or "[]")
        saida.append(d)
    return saida


def _ferramentas(p: dict) -> str:
    return " → ".join(c["ferramenta"] for c in p["chamadas"]) or "(nenhuma)"


def _falhou(p: dict) -> bool:
    return any(not r.get("ok") for r in p["resultado"])


def _curto(t: str, n: int) -> str:
    t = " ".join((t or "").split())
    return t if len(t) <= n else t[:n - 1] + "…"


def _resumo(pedidos: list[dict], dias: int) -> None:
    print(f"=== Assistente — últimos {dias} dias: {len(pedidos)} pedido(s) ===\n")
    if not pedidos:
        return
    print("Desfecho:  " + " · ".join(f"{k or '?'} {v}" for k, v in
                                     Counter(p["desfecho"] for p in pedidos).most_common()))
    print("Domínio:   " + " · ".join(f"{k or '?'} {v}" for k, v in
                                     Counter(p["dominios"] for p in pedidos).most_common()))
    com_ia = [p for p in pedidos if p["idas"]]
    if com_ia:
        ms = [p["ms"] for p in com_ia]
        print(f"Tempo:     médio {statistics.mean(ms) / 1000:.1f} s · maior {max(ms) / 1000:.1f} s")
        print(f"Idas à IA: média {statistics.mean(p['idas'] for p in com_ia):.1f} por pedido")
        print("Tokens por pedido (entrada+saída), por domínio:")
        por_dom: dict[str, list[int]] = {}
        for p in com_ia:
            por_dom.setdefault(p["dominios"], []).append(p["tokens_entrada"] + p["tokens_saida"])
        for dom, toks in sorted(por_dom.items()):
            print(f"  {dom:22} média {statistics.mean(toks):6.0f} · {len(toks)} pedido(s)")
    usadas = Counter(c["ferramenta"] for p in pedidos for c in p["chamadas"])
    if usadas:
        print("Ferramentas mais chamadas: " + " · ".join(f"{k} {v}" for k, v in usadas.most_common(8)))

    investigar = [p for p in pedidos if p["rede"] or p["desfecho"] == "erro" or _falhou(p)]
    print(f"\n--- PARA INVESTIGAR ({len(investigar)}) ---")
    for p in investigar:
        motivo = ("erro da IA: " + _curto(p["erro"], 80) if p["desfecho"] == "erro"
                  else "execução falhou" if _falhou(p)
                  else "roteador precisou mandar todas as ferramentas")
        print(f"{p['quando'][:16]}  {_curto(p['pedido'], 60)!r}\n"
              f"    {motivo} · domínio {p['dominios']} · {_ferramentas(p)}")


def _lista(pedidos: list[dict], n: int) -> None:
    print(f"\n--- ÚLTIMOS {min(n, len(pedidos))} ---")
    for p in pedidos[-n:]:
        res = "".join("✅" if r.get("ok") else "❌" for r in p["resultado"])
        print(f"{p['quando'][:16]}  [{p['dominios']}] {p['desfecho']} {res}\n"
              f"    {_curto(p['pedido'], 90)!r}\n    {_ferramentas(p)}")


def _csv(pedidos: list[dict], caminho: str) -> None:
    campos = ["quando", "matricula", "modelo", "pedido", "dominios", "rede", "idas",
              "tokens_entrada", "tokens_saida", "ms", "ferramentas", "chamadas",
              "resposta", "plano", "desfecho", "resultado", "erro"]
    # utf-8-sig + ';': abre direto no Excel em português com os acentos certos.
    with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for p in pedidos:
            w.writerow({**p, "ferramentas": _ferramentas(p),
                        "chamadas": json.dumps(p["chamadas"], ensure_ascii=False),
                        "resultado": json.dumps(p["resultado"], ensure_ascii=False)})
    print(f"\nExportado: {os.path.abspath(caminho)} ({len(pedidos)} pedido(s))")


def main() -> None:
    ap = argparse.ArgumentParser(description="Relatório dos pedidos ao Assistente.")
    ap.add_argument("--dias", type=int, default=30)
    ap.add_argument("--ultimos", type=int, default=10)
    ap.add_argument("--csv", metavar="ARQUIVO")
    a = ap.parse_args()
    pedidos = _carregar(a.dias)
    _resumo(pedidos, a.dias)
    if pedidos:
        _lista(pedidos, a.ultimos)
    if a.csv:
        _csv(pedidos, a.csv)


if __name__ == "__main__":
    main()
