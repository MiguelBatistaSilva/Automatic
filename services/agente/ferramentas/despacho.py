"""
services/agente/ferramentas/despacho.py — Despacho ao Serviço de Operações.

O script do despacho vem de services/agente/despacho_operacao.py. Roda pelo
fluxo do Aguardando Fornecedor (o mesmo _exec_lote das ações).

O técnico só diz o DEFEITO e, no periférico, o SERIAL (09/11). O resto o
sistema busca:
  - localização: campos do chamado (seção + 'Local:' da descrição ou Sala);
  - tombo da máquina: descrição do chamado ou Item B (um só; vários = pergunta);
  - marca, modelo e série do computador/notebook: Itom pelo tombo;
  - mouse e teclado: marca e modelo padrão (despacho_operacao.PADRAO_PERIFERICO);
  - OBS do periférico: o micro ao qual está vinculado (chamado + Itom).
O que o técnico disser vale mais que o que o sistema achou.
"""

from services.agente.ferramentas import base
from services.agente.ferramentas.acoes import _exec_lote
from services.agente.ferramentas.base import Acao, Ferramenta, _lista
from services.agente.sessao import Sessao


def _exec_despacho(a, s):
    """Mesma pausa do fornecedor, mas com o script FORMATADO (respostas em
    vermelho, 26/10). Cartão de antes disso (sem `campos`): texto todo azul."""
    import functools
    from services.agente import despacho_operacao as dop
    from services.fluxos.flow_fornecedor_pw import aguardar_info_fornecedor
    html = dop.montar_html(**a["campos"]) if a.get("campos") else None
    funcao = functools.partial(aguardar_info_fornecedor, conteudo_html=html)
    return _exec_lote(funcao, "Aguardando Info do Fornecedor", True, True)(a, s)


def _desc_despacho() -> str:
    """Só os NOMES dos modelos vão à IA; testes e defeito o código põe."""
    from services.agente import despacho_operacao as dop

    nomes = "; ".join(m.nome for m in dop.conhecimento.despachos()) or "(nenhum)"
    return ("DESPACHO ao Serviço de Operações (condenar/mandar equipamento para a "
            "Operação): pausa 'Aguardando Info do Fornecedor' com o script de "
            "despacho, que o SISTEMA monta. O sistema lê o chamado e o Itom "
            "(localização, tombo, marca, modelo e série da máquina): chame já com o "
            "que o técnico disse, sem perguntar antes. Escolha em defeito_modelo o "
            "modelo que casa com o defeito contado; não invente testes. Sem defeito "
            f"dito, chame sem defeito_modelo: o sistema diz o que perguntar. Modelos: {nomes}.")


def _antes_despacho(args: dict, s: Sessao) -> dict:
    """Lê o chamado (localização, tombos) e a máquina no Itom (09/11)."""
    from services.agente import despacho_operacao as dop, triagem
    from services.agente.ficha import ler_ficha

    out = dict(args)
    chamados = _lista(args.get("chamado"))
    tipo = dop.tipo_de(args.get("tipo") or "")
    tombos: list[str] = []
    f = ler_ficha(s.pagina, chamados[0], s.log) if len(chamados) == 1 else None
    if f is not None:
        out["_lido_do_chamado"] = True
        local = dop.localizacao(f.secao, f.sala, f.local_descrito, f.edificio)
        if local:
            out["_local"] = local
        tombos = list(f.tombos)
        do_item_b = triagem.tombo_do_item_b(f.item_b)
        if do_item_b and do_item_b not in tombos:
            tombos.append(do_item_b)
        out["_tombos_do_chamado"] = tombos

    # Que máquina olhar no Itom: o próprio computador/notebook, ou o micro do
    # periférico. Monitor e impressora não estão no Itom (o tombo é deles).
    if tipo in dop.NO_ITOM:
        dito = str(args.get("tombo") or "").strip()
    elif dop.periferico(tipo):
        dito = str(args.get("tombo_micro") or "").strip()
    else:
        return out
    alvo = dito or (tombos[0] if len(tombos) == 1 else "")
    if alvo:
        m = base._itom([alvo], s).get(alvo, False)
        out["_itom"] = {"tombo": alvo, "do_chamado": not dito,
                        # None = não está no Itom; False = não deu para entrar
                        "achou": None if m is None else bool(m),
                        "serial": getattr(m, "serial", "") or "",
                        "marca_modelo": getattr(m, "marca_modelo", "") or ""}
    return out


def _prep_despacho(args: dict) -> "Acao | str":
    """Despacho ao Serviço de Operações (20/10): a mesma pausa do fornecedor,
    com o script montado pelo código (services/agente/despacho_operacao.py)."""
    from services.agente import despacho_operacao as dop

    chamados = _lista(args.get("chamado"))
    if len(chamados) != 1:
        return "Falta o chamado (um só: o script é de um equipamento)."
    tipo = dop.tipo_de(args.get("tipo") or "")
    if not tipo:
        return f"Tipo de equipamento inválido. Válidos: {', '.join(dop.TIPOS)}."
    v = {k: str(args.get(k) or "").strip()
         for k in ("localizacao", "marca", "modelo", "serie", "tombo", "obs")}

    # ---- O que o sistema completa (o técnico disse = vale o dele) ---------- #
    origem: list[str] = []
    notas: list[str] = []   # para a pergunta à IA quando faltar algo
    if not v["localizacao"] and args.get("_local"):
        v["localizacao"] = args["_local"]
        origem.append("localização: do chamado")
    itom = args.get("_itom") or {}
    tombos_chamado = args.get("_tombos_do_chamado") or []
    if itom and itom["achou"] is None:
        notas.append(f"o tombo {itom['tombo']} não está no Itom")
    elif itom and itom["achou"] is False:
        notas.append("não consegui entrar no Itom")

    if tipo in dop.NO_ITOM:
        if not v["tombo"] and itom.get("tombo"):
            v["tombo"] = itom["tombo"]
            origem.append(f"tombo {v['tombo']}: do chamado")
        if itom.get("achou"):
            marca, modelo = dop.separar_marca_modelo(itom["marca_modelo"])
            vieram = []
            for k, rotulo, valor in (("marca", "marca", marca), ("modelo", "modelo", modelo),
                                     ("serie", "série", itom["serial"])):
                if not v[k] and valor:
                    v[k] = valor
                    vieram.append(rotulo)
            if vieram:
                origem.append(f"{', '.join(vieram)}: Itom (tombo {itom['tombo']})")
    if tipo in dop.PADRAO_PERIFERICO and not (v["marca"] or v["modelo"]):
        v["marca"], v["modelo"] = dop.PADRAO_PERIFERICO[tipo]
        origem.append(f"marca e modelo: padrão do {tipo.lower()}")

    vinculo = ""
    if dop.periferico(tipo) and itom.get("tombo"):
        vinculo = dop.vinculo_do_periferico(
            itom["tombo"], itom["marca_modelo"] if itom.get("achou") else "")
        origem.append(f"micro vinculado: tombo {itom['tombo']}"
                      + (" (do chamado)" if itom.get("do_chamado") else ""))

    # ---- O que ainda falta --------------------------------------------------- #
    serie_rot = f"nº de série do {tipo.lower()}" if dop.periferico(tipo) else "nº de série"
    faltam = [rot for k, rot in (("localizacao", "localização do equipamento"),
                                 ("marca", "marca"), ("modelo", "modelo"),
                                 ("serie", serie_rot)) if not v[k]]
    if dop.tem_tombo(tipo) and not v["tombo"]:
        faltam.append("tombo")
    if dop.periferico(tipo) and not vinculo:
        faltam.append("tombo do micro ao qual o periférico está ligado")
    varios = (len(tombos_chamado) > 1 and not itom
              and (tipo in dop.NO_ITOM or dop.periferico(tipo)))
    if varios:
        notas.append(f"o chamado tem os tombos {', '.join(tombos_chamado)}: pergunte "
                     "qual é " + ("o micro do periférico" if dop.periferico(tipo) else "a máquina"))

    testes = dop.itens(args.get("testes") or "")
    defeitos = dop.itens(args.get("defeito") or "")

    # Testes/defeito não ditos: saem do MODELO POR DEFEITO da equipe
    # (conhecimento/chamados/despachos.md, 26/10). A IA só escolhe o modelo;
    # se não deu para saber qual, pergunta junto com o que mais faltar.
    escolhido, pergunta = None, ""
    modelos = dop.modelos_de(tipo)
    if modelos and not (testes and defeitos):
        pelo_modelo = str(args.get("defeito_modelo") or "").strip()
        achados = dop.achar_modelo(tipo, pelo_modelo or " ".join(defeitos))
        if len(achados) == 1:
            escolhido = achados[0]
            if not pelo_modelo:
                # O "defeito" era só o problema contado ("botão direito"),
                # que serviu para achar o modelo: a conclusão vem dele.
                defeitos = []
        else:
            opcoes = achados or modelos
            pergunta = (f"Qual o defeito do {tipo.lower()}? Modelos: "
                        + "; ".join(m.nome for m in opcoes)
                        + " (ou ele dita os testes e o defeito)")
    if faltam or pergunta or varios:
        partes = ([f"Falta(m): {', '.join(faltam)}"] if faltam else []) + notas + \
                 ([pergunta] if pergunta else [])
        if args.get("_lido_do_chamado"):
            partes.append("O resto o sistema já leu do chamado e do Itom: não pergunte")
        return ". ".join(partes) + ". Pergunte ao técnico, de uma vez."

    pronto = []
    if escolhido:
        testes = testes or escolhido.testes
        defeitos = defeitos or [escolhido.defeito]
        aviso = f"Testes e defeito do modelo \"{escolhido.nome}\": confira."
    else:
        padrao_testes, padrao_defeitos = dop.SCRIPTS[tipo]
        pronto = [nome for nome, dito in (("testes", testes), ("defeito", defeitos)) if not dito]
        testes, defeitos = testes or padrao_testes, defeitos or padrao_defeitos
        aviso = (f"{' e '.join(pronto).capitalize()} "
                 f"{'vieram' if len(pronto) > 1 or pronto == ['testes'] else 'veio'} "
                 f"do script genérico de {tipo} (sem modelo da equipe): confira."
                 if pronto else "")
    obs = " ".join(x for x in (vinculo, v["obs"]) if x)
    campos = {"tipo": tipo, "localizacao": v["localizacao"], "marca": v["marca"],
              "modelo": v["modelo"], "serie": v["serie"],
              "testes": testes, "defeitos": defeitos,
              "tombo": v["tombo"], "obs": obs}
    texto = dop.montar_texto(**campos)
    linhas = [f"**Chamado:** {chamados[0]} · Aguardando Info do Fornecedor"]
    if origem:
        linhas.append("**Preenchido pelo sistema (confira):** " + "; ".join(origem) + ".")
    linhas.append(f"**Texto:**\n{texto}")
    return Acao(ferramenta="despachar_operacao",
                args={"chamados": chamados, "texto": texto, "campos": campos},
                titulo="Despacho ao Serviço de Operações",
                linhas=linhas, escreve=True, pode_simular=True, aviso=aviso)


# Catálogo deste arquivo (o __init__ junta todos, na ordem de _ORDEM).
FERRAMENTAS: list[Ferramenta] = [
    Ferramenta(
        "despachar_operacao",
        _desc_despacho,  # montada na hora: os nomes dos modelos de despacho
        {"type": "object", "properties": {
            "chamado": {"type": "string"},
            "tipo": {"type": "string", "description":
                     "Computador, Notebook, Monitor, Impressora, Teclado, Mouse, "
                     "Webcam ou Caixa de som."},
            "localizacao": {"type": "string", "description":
                            "Só se o técnico disser (o sistema lê do chamado)."},
            "marca": {"type": "string", "description": "Só se o técnico disser."},
            "modelo": {"type": "string", "description": "Só se o técnico disser."},
            "serie": {"type": "string", "description":
                      "Do periférico: o técnico diz. Do computador: o sistema busca no Itom."},
            "tombo": {"type": "string", "description":
                      "Do próprio equipamento (computador, notebook, monitor, impressora), "
                      "se o técnico disser."},
            "tombo_micro": {"type": "string", "description":
                            "Periférico: tombo do micro ao qual está ligado, se o técnico disser."},
            "obs": {"type": "string"},
            "defeito_modelo": {"type": "string", "description":
                               "Nome do modelo de despacho (lista na descrição) que "
                               "casa com o defeito que o técnico contou."},
            "testes": {"type": "string", "description":
                       "Um por linha. Só se o técnico DITAR os testes."},
            "defeito": {"type": "string", "description":
                        "Só se o técnico DITAR o texto do defeito; se ele só contou "
                        "o problema, use defeito_modelo."},
        }, "required": ["chamado", "tipo"]},
        preparar=_prep_despacho, executar=_exec_despacho,
        # Lê o chamado e o Itom (09/11): localização, tombo, máquina.
        antes=_antes_despacho,
        precisa_ler=lambda a: len(_lista(a.get("chamado"))) == 1,
        dominio="chamados",
    ),
]
