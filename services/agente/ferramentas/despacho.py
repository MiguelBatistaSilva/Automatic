"""
services/agente/ferramentas/despacho.py — Despacho ao Serviço de Operações.

O script do despacho vem de services/agente/despacho_operacao.py; a série
não dita vem do Itom pelo tombo. Roda pelo fluxo do Aguardando Fornecedor
(o mesmo _exec_lote das ações).
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
            "despacho, que o SISTEMA monta. Escolha em defeito_modelo o modelo que "
            "casa com o defeito contado; não invente testes. Sem defeito dito, "
            f"chame sem defeito_modelo: o sistema diz o que perguntar. Modelos: {nomes}.")


def _antes_despacho(args: dict, s: Sessao) -> dict:
    """Série não dita vem do Itom pelo tombo (30/10)."""
    tombo = str(args.get("tombo") or "").strip()
    m = base._itom([tombo], s).get(tombo, False)
    if m is None:
        return {**args, "_do_itom": f"o tombo {tombo} não está no Itom"}
    if m and m.serial:
        return {**args, "serie": m.serial, "_do_itom": f"série {m.serial} (tombo {tombo})"}
    return args


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
    faltam = [rot for k, rot in (("localizacao", "localização do equipamento"),
                                 ("marca", "marca"), ("modelo", "modelo"),
                                 ("serie", "nº de série")) if not v[k]]
    if dop.tem_tombo(tipo) and not v["tombo"]:
        faltam.append("tombo")
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
    if faltam or pergunta:
        partes = ([f"Falta(m): {', '.join(faltam)}"] if faltam else []) + \
                 ([pergunta] if pergunta else [])
        if "nº de série" in faltam and args.get("_do_itom"):
            partes.append(f"Itom: {args['_do_itom']}")
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
    if args.get("_do_itom") and v["serie"]:
        aviso = " ".join(x for x in (aviso, f"Do Itom: {args['_do_itom']}.") if x)
    campos = {"tipo": tipo, "localizacao": v["localizacao"], "marca": v["marca"],
              "modelo": v["modelo"], "serie": v["serie"],
              "testes": testes, "defeitos": defeitos,
              "tombo": v["tombo"], "obs": v["obs"]}
    texto = dop.montar_texto(**campos)
    return Acao(ferramenta="despachar_operacao",
                args={"chamados": chamados, "texto": texto, "campos": campos},
                titulo="Despacho ao Serviço de Operações",
                linhas=[f"**Chamado:** {chamados[0]} · Aguardando Info do Fornecedor",
                        f"**Texto:**\n{texto}"],
                escreve=True, pode_simular=True, aviso=aviso)


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
            "localizacao": {"type": "string", "description": "Dita pelo técnico."},
            "marca": {"type": "string"},
            "modelo": {"type": "string"},
            "serie": {"type": "string"},
            "tombo": {"type": "string", "description":
                      "Computador/Notebook/Monitor/Impressora. Teclado, mouse, "
                      "webcam e caixa de som não têm."},
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
        # Série não dita: o sistema busca no Itom pelo tombo (30/10).
        antes=_antes_despacho,
        precisa_ler=lambda a: bool(str(a.get("tombo") or "").strip())
        and not str(a.get("serie") or "").strip(),
        dominio="chamados",
    ),
]
