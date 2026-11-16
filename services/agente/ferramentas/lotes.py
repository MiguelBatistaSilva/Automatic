"""
services/agente/ferramentas/lotes.py — Retomar um lote pela metade (16/11).

"Retoma o fluxo de base" sem dizer chamados nem base: a ferramenta lista os
lotes do técnico que ficaram pela metade (os mesmos do botão "Retomar" da
página "Meus fluxos"), com a base e o andamento de cada um. Com o lote
escolhido, monta o cartão da ferramenta de sempre (aplicar_base, desmembrar,
anexar_itom) com os dados guardados — o cartão já sai com "Retomar", porque o
checkpoint está pela metade, e a execução é a mesma de sempre.

De onde vêm os dados: services/dados/memoria_lote.py (tabela `lotes`, gravada
quando o lote roda pelo app ou pelo agente). Lote de antes de 16/11 não tem.

Corrigir Item B e Importar documento do app (16/11): o agente não tem
ferramenta igual (o corrigir_item_b dele decide o tombo pela regra e guarda
outra memória), então o cartão é do próprio retomar_lote e a execução é a do
app — o tombo que o técnico colou / o PDF que ele enviou, a MESMA memória do
lote — na página da Sessao (com Simular).
"""

from services.agente.ferramentas.base import Acao, Ferramenta, _lista_curta
from services.agente.sessao import Resultado, Sessao

# modo da tela -> (rótulo, palavra que o técnico usa)
_MODOS = {
    "bc":       ("Aplicar base", "base"),
    "completo": ("Desmembrar + base", "desmembrar"),
    "criar":    ("Desmembrar", "desmembrar"),
    "itom":     ("Adicionar Itom", "itom"),
    "itemb":    ("Corrigir Item B (app)", "item b"),
    "doc":      ("Importar documento (app)", "documento"),
}
# O que conta como feito na memória (as mesmas do state/desmembramento_state.py).
_FEITO = {"itemb": ("corrigido", "já estava certo", "não corrigido"),
          "doc": ("anexado", "já anexado")}


def _pendentes(matricula: str) -> list[tuple[dict, dict]]:
    """[(rodada, parâmetros)] dos lotes vigentes pela metade, mais novo primeiro."""
    from services.dados import checkpoint, memoria_lote

    hist = [h for h in checkpoint.historico(matricula)
            if h["vigente"] and not h["concluido"]
            and (h["fluxo"] or "").startswith("desmembramento")]
    com = memoria_lote.chaves_com_parametros([h["chave"] for h in hist])
    return [(h, memoria_lote.parametros(h["chave"])) for h in hist if h["chave"] in com]


def _tombos_do_csv(csv_texto: str) -> list[str] | None:
    """Tombos do CSV de uma coluna só ('tombo', como o agente grava). CSV da
    tela com mais colunas: None (só dá para retomar pelo "Meus fluxos")."""
    linhas = [l.strip() for l in (csv_texto or "").splitlines() if l.strip()]
    if not linhas or linhas[0].lower() != "tombo":
        return None
    return linhas[1:]


def _descrever(h: dict, p: dict) -> str:
    rotulo = _MODOS.get(p.get("modo"), (p.get("modo") or "?", ""))[0]
    feitas = sum(1 for l in h["linhas"] if l["status"] == "concluido")
    partes = [f"#{h['id']} {rotulo}"]
    if p.get("kb"):
        partes.append(f"base '{p['kb']}'")
    if p.get("chamado_pai"):
        partes.append(f"pai {p['chamado_pai']}")
    else:
        refs = [l.get("referencia", "") for l in h["linhas"] if l.get("referencia")]
        if refs:
            partes.append(f"chamados {_lista_curta(refs)}")
    partes.append(f"{feitas} de {h['total']} feitos, desde {h['criado_em']}")
    return " · ".join(partes)


def _prep_retomar(args: dict) -> "Acao | str":
    matricula = args.get("_matricula") or ""
    if not matricula:
        return "Não sei quem é o técnico (credenciais não cadastradas). Avise."
    lotes = _pendentes(matricula)
    tipo = str(args.get("tipo") or "").strip().lower()
    if tipo:
        # Pela palavra do tipo: "base" é o Aplicar base, não o Desmembrar + base.
        lotes = [(h, p) for h, p in lotes
                 if _MODOS.get(p.get("modo"), ("", "?"))[1].startswith(tipo[:6])]
    escolhido = str(args.get("lote") or "").strip().lstrip("#")

    if not escolhido:
        if not lotes:
            return ("Nenhum lote pela metade" + (f" de '{tipo}'" if tipo else "")
                    + ". Diga isso ao técnico (lotes de antes de 16/11 não ficam guardados).")
        if len(lotes) > 1:
            return ("Lotes pela metade (mais novo primeiro):\n- "
                    + "\n- ".join(_descrever(h, p) for h, p in lotes)
                    + "\nMostre a lista e pergunte qual retomar; depois chame de novo com "
                      "lote = o número depois do #.")
        escolhido = str(lotes[0][0]["id"])

    achado = next(((h, p) for h, p in _pendentes(matricula) if str(h["id"]) == escolhido), None)
    if achado is None:
        return f"Não achei o lote #{escolhido} pela metade. Chame sem lote para ver a lista."
    h, p = achado
    if p.get("modo") in _FEITO:
        return _cartao_do_app(h, p)
    return _cartao(h, p)


# --------------------------------------------------------------------------- #
# Corrigir Item B e Importar documento do app
# --------------------------------------------------------------------------- #

def _cartao_do_app(h: dict, p: dict) -> "Acao | str":
    import os
    from services.dados import memoria_lote
    from services.fluxos.flow_anexo_itom_pw import ler_chamados, ler_pares

    modo = p["modo"]
    # Os itens do mesmo jeito que a tela monta (state/desmembramento_state._lote).
    if modo == "itemb":
        linhas = ler_pares(p.get("itemb_texto", ""))[0]
        refs = [l.chamado for l in linhas]
        itens = [f"{l.chamado},{l.tombo}" for l in linhas]
        o_que = [f"{l.chamado}: Item B → *{l.tombo}" for l in linhas]
        titulo = "Corrigir Item B (lote do app)"
    else:
        refs = ler_chamados(p.get("doc_chamados", ""))[0]
        itens = [f"{c},{p.get('doc_nome', '')}" for c in refs]
        o_que = list(refs)
        titulo = "Importar documento (lote do app)"
        if not os.path.exists(p.get("doc_caminho", "")):
            return (f"O documento {p.get('doc_nome', '')} do lote #{h['id']} não está mais no "
                    "computador. Diga ao técnico para enviá-lo de novo pela tela do "
                    "Desmembramento (Importar documento).")
    if len(itens) != h["total"]:
        return f"Os dados do lote #{h['id']} não batem com o andamento guardado. Retome pelo app."
    feitos = {l["index"] for l in h["linhas"] if l["status"] == "concluido"}
    faltam = [o for i, o in enumerate(o_que) if i not in feitos]
    linhas_cartao = [f"**Faltam {len(faltam)} de {len(itens)}:**\n" + "\n".join(f"- {o}" for o in faltam)]
    if modo == "doc":
        linhas_cartao.insert(0, f"**Documento:** {p.get('doc_nome', '')}")
    return Acao(ferramenta="retomar_lote",
                args={"modo": modo, "chave": h["chave"], "itens": itens, "refs": refs,
                      "pdf": p.get("doc_caminho", "")},
                titulo=titulo, linhas=linhas_cartao, escreve=True, pode_simular=True,
                checkpoint=memoria_lote.situacao(h["chave"]),
                aviso=memoria_lote.resumo(h["chave"]))


def _exec_do_app(a: dict, s: Sessao) -> Resultado:
    """Como o app roda (o tombo colado / o PDF enviado), na página da Sessao,
    anotando cada chamado na memória do lote na hora. Simular não anota."""
    from services.agente.ficha import esquecer
    from services.dados import checkpoint, memoria_lote
    from services.fluxos import flow_anexo_itom_pw as anexo
    from services.fluxos.flow_corrigir_chamado_pw import corrigir_chamado

    modo, k, itens, refs = a["modo"], a["chave"], a["itens"], a["refs"]
    if s.modo_teste:
        feitos = {l["index"] for l in checkpoint.status_linhas(k) if l["status"] == "concluido"}
    else:
        feitos = memoria_lote.abrir(k, itens, refs, fluxo=f"desmembramento_{modo}",
                                    origem="bot" if s.chat_id else "ui",
                                    matricula=s.matricula, do_zero=s.iniciar_do_zero)
    corpo, n_ok = [], 0
    for i, chamado in enumerate(refs):
        if i in feitos:
            corpo.append(f"- ✅ {chamado} — já feito antes")
            n_ok += 1
            continue
        if modo == "itemb":
            tombo = itens[i].split(",", 1)[1]
            s.log(f"Corrigindo o Item B do {chamado} (tombo {tombo})...", "status")
            try:
                ok, info = corrigir_chamado(s.pagina(), s.log, chamado, item_b=f"*{tombo}",
                                            modo_teste=s.modo_teste)
            except Exception as e:
                ok, info = False, {"erro": str(e)}
            esquecer(chamado)
            if not ok:
                situacao, detalhe = "erro", info.get("erro", "")
            elif info.get("mudou"):
                antes, depois = info["mudou"]["Item B"]
                situacao, detalhe = "corrigido", f"{antes or '(vazio)'} → {depois}"
            elif info.get("aviso"):
                situacao, detalhe = "não corrigido", info["aviso"]
            else:
                situacao, detalhe = "já estava certo", ""
        else:
            l = anexo.Linha(chamado, "", pdf=a["pdf"])
            try:
                anexo.anexar(s.pagina(), s.log, l, s.modo_teste)
            except Exception as e:
                l.situacao, l.detalhe = "erro", str(e)
            situacao, detalhe = l.situacao, (l.detalhe if l.situacao == "erro" else "")
        if not s.modo_teste and situacao in _FEITO[modo]:
            memoria_lote.marcar(k, i, situacao=situacao)
        marca = "❌" if situacao == "erro" else "⚠️" if situacao == "não corrigido" else "✅"
        n_ok += marca == "✅"
        corpo.append(f"- {marca} {chamado} — {situacao}" + (f" ({detalhe})" if detalhe else ""))
    sufixo = " (simulação, nada salvo)" if s.modo_teste else ""
    titulo = "Corrigir Item B" if modo == "itemb" else "Importar documento"
    cab = f"**{titulo}{sufixo}** — {n_ok} de {len(refs)}."
    return Resultado("\n".join([cab] + corpo), ok=all("❌" not in c for c in corpo))


def _cartao(h: dict, p: dict) -> "Acao | str":
    from bot.services import desmembramento_service as ds
    from services.agente.ferramentas import bases
    from services.dados import memoria_lote

    modo = p["modo"]
    if modo == "bc":
        chamados = [c.strip() for c in p.get("filhos_texto", "").splitlines() if c.strip()]
        return bases._prep_aplicar_base({"chamados": chamados, "base": p.get("kb", "")})

    if modo in ("completo", "criar"):
        tombos = _tombos_do_csv(p.get("csv_texto", ""))
        if tombos is None:
            return (f"O lote #{h['id']} veio da tela com uma planilha de várias colunas: "
                    "retome pela página 'Meus fluxos', botão Retomar. Diga isso ao técnico.")
        pai = p.get("chamado_pai", "")
        base = p.get("kb") if modo == "completo" else None
        sit = ds.situacao(pai)
        linhas = [f"**Chamado pai:** {pai}",
                  f"**Tombos:** {len(tombos)} ({_lista_curta(tombos)})",
                  f"**Descrição dos filhos:** {p.get('descricao', '')}"]
        if base:
            linhas.append(f"**Base:** {base}")
        return Acao(ferramenta="desmembrar",
                    args={"chamado_pai": pai, "tombos": tombos,
                          "descricao": p.get("descricao", ""), "base": base},
                    titulo="Desmembramento", linhas=linhas, escreve=True,
                    checkpoint=sit["estado"], aviso=sit.get("resumo", ""))

    if modo == "itom":
        from services.agente.ferramentas.por_fila import _chave_itom
        from services.fluxos.flow_anexo_itom_pw import ler_pares
        pares = {l.chamado: l.tombo for l in ler_pares(p.get("itom_texto", ""))[0]}
        k = _chave_itom(pares)
        return Acao(ferramenta="anexar_itom",
                    args={"chamados": list(pares), "pares": pares},
                    titulo="Adicionar Itom",
                    linhas=["**Fazer:**\n" + "\n".join(f"- {c}: tombo {t}" for c, t in pares.items())],
                    escreve=True, pode_simular=True,
                    checkpoint=memoria_lote.situacao(k), aviso=memoria_lote.resumo(k))
    return f"Não sei retomar o lote #{h['id']} ({modo})."


FERRAMENTAS: list[Ferramenta] = [
    Ferramenta(
        "retomar_lote",
        "Retoma um lote que ficou pela metade (aplicar base, desmembrar, Itom, Item B, "
        "documento) sem o "
        "técnico dizer chamados nem base: sem 'lote', o sistema lista os pendentes "
        "com a base de cada um; com 'lote', monta o cartão de Retomar.",
        {"type": "object", "properties": {
            "tipo": {"type": "string", "description":
                     "Só se o técnico disse: 'base', 'desmembrar', 'itom', 'item b' "
                     "ou 'documento'."},
            "lote": {"type": "string", "description":
                     "O número (#) do lote que o técnico escolheu na lista."},
        }},
        # executar: só para Corrigir Item B e Importar documento do app; os
        # outros cartões são das ferramentas de sempre.
        preparar=_prep_retomar, executar=_exec_do_app, com_matricula=True,
        dominio="chamados",
    ),
]
