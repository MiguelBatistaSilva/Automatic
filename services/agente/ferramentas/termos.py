"""
services/agente/ferramentas/termos.py — Os termos gerados no computador do técnico.

Termo de Responsabilidade de Instalação (troca de máquina; marca/modelo,
série e hostname vêm do Itom pelo tombo) e Termo de Tarefa de Demanda
(eventos; extração por regex, a IA não vê a descrição). Nenhum dos dois
escreve no Assyst: o PDF é assinado e anexado à mão.
"""

import copy
import datetime
import difflib
import re

from services.agente.ferramentas import base
from services.agente.ferramentas.base import Acao, Ferramenta
from services.agente.sessao import Resultado, Sessao


# --------------------------------------------------------------------------- #
# Termo de Responsabilidade de Instalação (troca de máquina) — 10/10
# --------------------------------------------------------------------------- #
#
# Roda no computador do técnico (services/termos): não mexe no Assyst. O que
# vem do chamado (nome, matrícula e unidade do usuário afetado) é lido pelo
# CÓDIGO em `_antes_termo` e vai direto para o cartão — a IA não vê a
# matrícula. O que o técnico não souber sai em branco no documento.

_CAMPOS_EQUIP = ("marca_modelo", "tombo", "serie", "hostname")


# Repetido em "saiu" e "entrou" (sem $ref: o Gemini não aceita).
_EQUIP_ESQUEMA = {"type": "object", "properties": {
    "marca_modelo": {"type": "string", "description": "Só se o técnico disser. Ex.: POSITIVO C6200. Sem o tombo."},
    "tombo": {"type": "string", "description": "Patrimônio: só números, em geral 6 dígitos."},
    "serie": {"type": "string", "description": "Nº de série: letras e números (ex.: 1AM03Y878)."},
    "hostname": {"type": "string", "description":
                 "Nome da máquina na rede (ex.: FCB13CRIM). 'Coloque o nome X' = hostname."},
}}


# Marcas na grafia do patrimônio; erro de digitação ("Lennovo") cai na mais
# parecida.
_MARCAS = ("POSITIVO", "LENOVO", "DELL", "HP", "DATEN", "ITAUTEC", "ACER", "SAMSUNG", "LG")


_RE_TOMBO = re.compile(r"\b\d{5,7}\b")


# Modelo solto (C6200, M70Q) que a IA pôs no hostname. Hostname do TJ é maior
# (FCB13CRIM), então não casa.
_RE_MODELO = re.compile(r"^[A-Za-z]{1,2}\d{3,4}[A-Za-z]?$")


_RE_HOSTNAME = re.compile(r"^(?=.*\d)[A-Za-z0-9-]{6,}$")


def _equip(v) -> dict:
    v = v if isinstance(v, dict) else {}
    e = {k: re.sub(r"\s+", " ", str(v.get(k) or "")).strip() for k in _CAMPOS_EQUIP}
    if not e["marca_modelo"] and _RE_MODELO.match(e["hostname"]):
        e["marca_modelo"], e["hostname"] = e["hostname"], ""
    # Tombo grudado no modelo ("Lenovo 333232"): separa.
    numeros = _RE_TOMBO.findall(e["marca_modelo"])
    if numeros and (not e["tombo"] or e["tombo"] in numeros):
        e["tombo"] = e["tombo"] or numeros[0]
        e["marca_modelo"] = " ".join(_RE_TOMBO.sub(" ", e["marca_modelo"]).split())
    palavras = e["marca_modelo"].split(" ", 1)
    marca = difflib.get_close_matches(palavras[0].upper(), _MARCAS, n=1, cutoff=0.75)
    if marca:
        e["marca_modelo"] = " ".join([marca[0], *palavras[1:]])
    e["hostname"] = e["hostname"].upper()
    return e


def _arrumar_trocas(trocas: list[dict], hostname: str, so_entrou: tuple = ()) -> None:
    """Na troca a máquina nova herda o nome da antiga: hostname dito só de um
    lado (ou solto no pedido) vale para os dois. `so_entrou`: tombos que entraram
    com o nome do Itom; esse nome é da nova, não vai para a que saiu."""
    solto = hostname if len(trocas) == 1 else ""
    for t in trocas:
        um = t["saiu"]["hostname"] or t["entrou"]["hostname"] or solto
        if t["entrou"]["tombo"] not in so_entrou:
            t["saiu"]["hostname"] = t["saiu"]["hostname"] or um
        t["entrou"]["hostname"] = t["entrou"]["hostname"] or um


def _hostname_fora_do_nome(args: dict) -> dict:
    """"Coloque o nome FCB13CRIM" virava o NOME DO USUÁRIO no termo (21/10):
    `nome` com cara de hostname sai do nome e vai para `_hostname`."""
    nome = str(args.get("nome") or "").strip()
    if " " in nome or not _RE_HOSTNAME.match(nome):
        return args
    return {**args, "nome": "", "_hostname": nome.upper()}


def _maquinas_do_itom(args: dict, s: Sessao) -> dict:
    """Marca/modelo, série e hostname que o técnico não disse vêm do Itom pelo
    tombo, dos dois lados (05/11). Hostname ditado vale para a troca toda (_arrumar_trocas). A que
    entrou e não está no Itom herda o nome da antiga."""
    trocas = [{"saiu": _equip(m.get("saiu")), "entrou": _equip(m.get("entrou"))}
              for m in (args.get("maquinas") or []) if isinstance(m, dict)]
    solto = bool(args.get("_hostname")) and len(trocas) == 1

    def sem_nome(t: dict) -> bool:
        return not (solto or t["saiu"]["hostname"] or t["entrou"]["hostname"])

    pedir = [e["tombo"] for t in trocas for e in t.values() if e["tombo"]
             and (not e["serie"] or not e["marca_modelo"] or sem_nome(t))]
    if not pedir:
        return args
    achados, notas, so_entrou = base._itom(pedir, s), [], []
    antes = copy.deepcopy(trocas)
    if not achados:
        return {**args, "maquinas": trocas, "_itom_fora": True}
    for t in trocas:
        buscar_nome = sem_nome(t)
        for e in t.values():
            m = achados.get(e["tombo"]) if e["tombo"] else None
            if e["tombo"] in pedir and e["tombo"] in achados and m is None:
                notas.append(f"tombo {e['tombo']} não está no Itom")
            if not m:
                continue
            if not e["serie"] and m.serial:
                e["serie"] = m.serial
            if not e["marca_modelo"] and m.marca_modelo:
                e["marca_modelo"] = m.marca_modelo
            if buscar_nome and m.hostname:
                e["hostname"] = m.hostname
        if buscar_nome and t["entrou"]["hostname"] and not t["saiu"]["hostname"]:
            so_entrou.append(t["entrou"]["tombo"])
    if trocas != antes:
        notas.append("dados preenchidos, confira no cartão")
    return {**args, "maquinas": trocas, "_do_itom": notas, "_nome_so_entrou": so_entrou}


def _saiu_do_chamado(args: dict, f) -> dict:
    """Tombo da máquina que SAIU, não dito pelo técnico, vem do chamado (30/10):
    do Item B (FJE06JECC332154) ou, se lá não tiver, do ÚNICO tombo da
    descrição. Vários na descrição: `_tombos_saiu` vira pergunta no preparar."""
    from services.agente.triagem import tombo_do_item_b, tombos_da_descricao

    if f is None:
        return args
    maquinas = [m for m in (args.get("maquinas") or []) if isinstance(m, dict)]
    if len(maquinas) > 1 or (maquinas and _equip(maquinas[0].get("saiu"))["tombo"]):
        return args
    tombo = tombo_do_item_b(f.item_b)
    if not tombo:
        da_descricao = tombos_da_descricao(f.descricao)
        if len(da_descricao) > 1:
            return {**args, "_tombos_saiu": da_descricao}
        tombo = da_descricao[0] if da_descricao else ""
    if not tombo:
        return args
    if maquinas:
        saiu = {**(maquinas[0].get("saiu") or {}), "tombo": tombo}
        return {**args, "maquinas": [{**maquinas[0], "saiu": saiu}], "_saiu_do_chamado": tombo}
    # Sem máquinas no pedido: a que saiu é a do chamado; falta a que entrou.
    return {**args, "maquinas": [{"saiu": {"tombo": tombo}, "entrou": {}}],
            "_saiu_do_chamado": tombo, "_perguntar_entrou": True}


def _antes_termo(args: dict, s: Sessao) -> dict:
    """Lê nome, matrícula e unidade do usuário afetado do chamado. O que o
    técnico disse na conversa vale mais que o lido. Série e hostname que
    faltarem vêm do Itom (30/10)."""
    from services.assyst.assyst_common import _so_o_nome
    from services.agente.ficha import ler_ficha

    args = _hostname_fora_do_nome(args)
    f = ler_ficha(s.pagina, str(args.get("chamado") or ""), s.log)
    args = _maquinas_do_itom(_saiu_do_chamado(args, f), s)
    if f is None:
        return args
    return _completar(args, {"matricula": f.afetado_matricula, "nome": f.afetado_nome,
                             "unidade": _so_o_nome(f.secao) if f.secao else ""})


def _completar(args: dict, lido: dict) -> dict:
    """O lido do chamado preenche só o que o técnico NÃO disse na conversa."""
    return {**args, **{k: v for k, v in lido.items()
                       if v and not str(args.get(k) or "").strip()},
            "_lido_do_chamado": True}


def _prep_termo(args: dict) -> "Acao | str":
    if not isinstance(args.get("backup"), bool):
        return "Falta saber se foi COM ou SEM backup. Pergunte."
    trocas = [{"saiu": _equip(m.get("saiu")), "entrou": _equip(m.get("entrou"))}
              for m in (args.get("maquinas") or []) if isinstance(m, dict)]
    trocas = [t for t in trocas if any(t["saiu"].values()) or any(t["entrou"].values())]
    # A que saiu veio do chamado (30/10): só falta a que entrou.
    if args.get("_tombos_saiu") and not any(t["saiu"]["tombo"] for t in trocas):
        return (f"O chamado cita os tombos {', '.join(args['_tombos_saiu'])}. Pergunte qual "
                "SAIU e o tombo da que ENTROU (o resto o sistema busca no Itom).")
    if args.get("_perguntar_entrou") and trocas:
        s = trocas[0]["saiu"]
        do_itom = ", ".join(f"{r} {s[k]}" for k, r in (("serie", "série"), ("hostname", "hostname")) if s[k])
        return (f"A máquina que SAIU é a do chamado: tombo {s['tombo']}"
                + (f" ({do_itom}, do Itom)" if do_itom else "") + ". Pergunte só a que "
                "ENTROU (só o tombo; o resto o sistema busca no Itom) e "
                f"chame de novo com saiu.tombo={s['tombo']}. Se ele não souber, gere com a "
                "que entrou em branco.")
    if not trocas:
        return ("Faltam as máquinas trocadas. Pergunte, de uma vez, para cada troca: "
                "o tombo da que saiu e o da que entrou. O resto o sistema busca no Itom.")
    args = _hostname_fora_do_nome(args)
    _arrumar_trocas(trocas, args.get("_hostname", ""), tuple(args.get("_nome_so_entrou") or ()))
    a = {
        "chamado": str(args.get("chamado") or "").strip().upper(),
        "backup": args["backup"],
        "maquinas": trocas,
        **{k: str(args.get(k) or "").strip() for k in ("nome", "matricula", "unidade",
                                                        "observacoes")},
        "onedrive": args.get("onedrive") if isinstance(args.get("onedrive"), bool) else None,
    }

    def ou_branco(v: str) -> str:
        return v or "*(em branco)*"

    def maquina(e: dict) -> str:
        partes = [f"{rotulo} {e[k]}" for k, rotulo in
                  (("tombo", "tombo"), ("serie", "série"), ("hostname", "hostname")) if e[k]]
        dados = ", ".join(partes)
        if not e["marca_modelo"]:
            return dados or "?"
        return f"{e['marca_modelo']} ({dados})" if dados else e["marca_modelo"]

    linhas = [
        f"**Chamado:** {ou_branco(a['chamado'])} · **Data:** "
        f"{datetime.date.today():%d/%m/%Y}",
        f"**Tipo:** {'Com' if a['backup'] else 'Sem'} backup e restore",
        f"**Usuário:** {ou_branco(a['nome'])} · **Matrícula:** {ou_branco(a['matricula'])}",
        f"**Unidade:** {ou_branco(a['unidade'])}",
    ]
    if a["backup"]:
        linhas.append("**Backup pelo OneDrive oferecido?** " + (
            "não marcado" if a["onedrive"] is None else ("Sim" if a["onedrive"] else "Não")))
    for n, t in enumerate(trocas, 1):
        rotulo = f"Máquina {n}" if len(trocas) > 1 else "Máquina"
        linhas.append(f"**{rotulo}:** {maquina(t['saiu'])} → {maquina(t['entrou'])}")
    if a["observacoes"]:
        linhas.append(f"**Observações:** {a['observacoes']}")
    aviso = ""
    if a["chamado"] and not args.get("_lido_do_chamado"):
        aviso = "Não consegui ler o usuário afetado do chamado: confira nome, matrícula e unidade."
    if args.get("_do_itom"):
        aviso = " ".join(x for x in (aviso, "Do Itom: " + "; ".join(args["_do_itom"]) + ".") if x)
    if args.get("_itom_fora"):
        aviso = " ".join(x for x in (aviso, "Não consegui consultar o Itom: o que o técnico "
                                     "não disse ficou em branco.") if x)
    return Acao(ferramenta="gerar_termo", args=a,
                titulo="Termo de Responsabilidade de Instalação", linhas=linhas,
                escreve=True,
                # "Simular" gera o termo igual (é local): o botão só existe
                # para não sumir de um plano junto com passos do Assyst.
                pode_simular=True, assyst=False, aviso=aviso)


def _termo_de(a: dict):
    from services import termos
    return termos.Termo(
        backup=a["backup"], unidade=a["unidade"], chamado=a["chamado"],
        data=datetime.date.today(),
        trocas=[termos.Troca(termos.Equipamento(**t["saiu"]),
                             termos.Equipamento(**t["entrou"])) for t in a["maquinas"]],
        recebedor=termos.Pessoa(a["nome"], a["matricula"]),
        onedrive=a["onedrive"], observacoes=a["observacoes"])


def _exec_termo(a: dict, s: Sessao) -> Resultado:
    from services import termos
    s.log("Gerando o termo...", "status")
    try:
        odt, pdf, erro_pdf = termos.gerar(_termo_de(a))
    except Exception as e:
        return Resultado(f"❌ Não consegui gerar o termo: {e}", ok=False)
    ref = f" do {a['chamado']}" if a["chamado"] else ""
    if pdf is None:
        return Resultado(f"⚠️ **Termo{ref} gerado só em ODT** — o PDF falhou ({erro_pdf}).",
                         arquivos=[str(odt)])
    return Resultado(f"✅ **Termo{ref} gerado.**", arquivos=[str(pdf), str(odt)])


# --------------------------------------------------------------------------- #
# Termo de Tarefa de Demanda (eventos) — 10/10
# --------------------------------------------------------------------------- #
#
# Quase tudo vem do chamado, lido pelo CÓDIGO (`_antes_demanda`): solicitante,
# Início/Fim agendado, nome do técnico e a DESCRIÇÃO — de onde saem o local e
# a descrição do evento (services/termos/demanda.py). A descrição NUNCA vai
# para a IA: no fim dela vem colado CPF, telefone e nascimento do solicitante.
# Do técnico: validador, horário real do evento e OBS.

def _hora(v) -> str:
    """'10h' / '10:00' / '9h30' / '9' -> 'hh:mm'; o resto passa como veio."""
    t = str(v or "").strip()
    m = re.fullmatch(r"(\d{1,2})\s*(?:[:h]\s*(\d{2})?)?\s*(?:h|hs|horas)?", t, re.I)
    if not m or int(m[1]) > 23:
        return t
    return f"{int(m[1]):02d}:{m[2] or '00'}"


def _antes_demanda(args: dict, s: Sessao) -> dict:
    """Tudo pela FICHA do chamado (services/agente/ficha.py, 23/10). O local segue a
    regra única: técnico/IA > 'Local:' na descrição > (a IA lê do Pedido) >
    Edifício + Sala do chamado — os dois últimos resolvidos no _prep_demanda."""
    from services.agente.ficha import ler_ficha
    from services.termos.demanda import nome_proprio

    f = ler_ficha(s.pagina, str(args.get("chamado") or ""), s.log)
    if f is None:
        return args
    dito = str(args.get("local") or "").strip()
    out = _completar(args, {
        "solicitante": nome_proprio(f.afetado_nome),
        "data": f.inicio_data,
        "inicio_previsto": f.inicio_hora,
        "fim_previsto": f.fim_hora,
        "local": f.local_descrito,
        "descricao": f.evento,
        "tecnico_nome": f.tecnico_logado,
        "tecnico_matricula": s.matricula,
    })
    out["_origem_local"] = "" if dito else ("descrição" if f.local_descrito else "")
    out["_local_chamado"] = f.local_do_chamado
    out["_pedido"] = f.pedido
    return out


_CAMPOS_DEMANDA = ("chamado", "solicitante", "data", "inicio_previsto", "fim_previsto",
                   "local", "descricao", "validador_nome", "validador_matricula",
                   "inicio", "fim", "obs", "tecnico_nome", "tecnico_matricula")


def _prep_demanda(args: dict) -> "Acao | str":
    a = {k: str(args.get(k) or "").strip() for k in _CAMPOS_DEMANDA}
    a["chamado"] = a["chamado"].upper()
    if not a["chamado"]:
        return "Falta o número do chamado do evento (os dados do evento vêm dele)."
    if not a["validador_nome"] and args.get("validador_a_mao") is not True:
        # Sem isto o modelo gerava direto, com o validador em branco (teste
        # de 10/10): só o técnico sabe quem validou — tem que perguntar.
        faltam = ["quem foi o VALIDADOR (nome e matrícula)"]
        if not (a["inicio"] or a["fim"]):
            faltam.append("o horário em que ele COMEÇOU e TERMINOU de fato")
        if not a["obs"]:
            faltam.append("a OBS (o que ele fez no evento)")
        pedido = str(args.get("_pedido") or "")
        local = ("" if a["local"] or not pedido else
                 " Na próxima chamada, passe também `local` = onde é o evento, se o "
                 f'Pedido do chamado disser (não pergunte isso ao técnico): "{pedido}"')
        return ("Antes de gerar, pergunte ao técnico numa mensagem só: "
                + "; ".join(faltam) + ". Se ele disser que o validador vai ser "
                "preenchido à mão, chame de novo com validador_a_mao=true." + local)
    for k in ("inicio_previsto", "fim_previsto", "inicio", "fim"):
        a[k] = _hora(a[k])
    # Regra única do local (23/10): técnico/IA > descrição > Edifício + Sala.
    nota_local = "da descrição" if args.get("_origem_local") == "descrição" else ""
    if not a["local"] and args.get("_local_chamado"):
        a["local"], nota_local = args["_local_chamado"], "do Edifício/Sala do chamado"

    def ou_branco(v: str, motivo: str = "") -> str:
        return v or f"*(em branco{' — ' + motivo if motivo else ''})*"

    previsto = f"{a['inicio_previsto'] or '?'} às {a['fim_previsto'] or '?'}"
    execucao = (f"{a['inicio'] or a['inicio_previsto'] or '?'} às "
                f"{a['fim'] or a['fim_previsto'] or '?'}")
    if not (a["inicio"] or a["fim"]):
        execucao += " *(o agendado — o técnico não informou)*"
    tecnico = a["tecnico_nome"] + (f" — mat. {a['tecnico_matricula']}"
                                   if a["tecnico_matricula"] else "")
    linhas = [
        f"**Chamado:** {a['chamado']} · **Data do serviço:** {ou_branco(a['data'])}",
        f"**Solicitante/Requisitante:** {ou_branco(a['solicitante'])}",
        f"**Local:** {ou_branco(a['local'], 'não achei no chamado')}"
        + (f" *({nota_local})*" if a["local"] and nota_local else ""),
        f"**Horário previsto:** {previsto}",
        f"**Descrição do evento:** {ou_branco(a['descricao'], 'não achei na descrição')}",
        f"**Validador:** {ou_branco(a['validador_nome'])} · "
        f"**Matrícula:** {ou_branco(a['validador_matricula'])}",
        f"**Horário de execução:** {execucao}",
        f"**Técnico:** {ou_branco(tecnico)}",
        f"**OBS:** {ou_branco(a['obs'])}",
    ]
    aviso = "" if args.get("_lido_do_chamado") else (
        "Não consegui ler o chamado no Assyst: os dados do evento vão em branco.")
    return Acao(ferramenta="gerar_termo_demanda", args=a,
                titulo="Termo de Tarefa de Demanda", linhas=linhas, escreve=True,
                pode_simular=True, assyst=False, aviso=aviso)


def _exec_demanda(a: dict, s: Sessao) -> Resultado:
    from services import termos
    from services.termos.demanda import TermoDemanda
    s.log("Gerando o termo de demanda...", "status")
    try:
        data = datetime.datetime.strptime(a["data"], "%d/%m/%Y").date() if a["data"] else None
    except ValueError:
        data = None
    t = TermoDemanda(
        chamado=a["chamado"], solicitante=a["solicitante"], local=a["local"], data=data,
        inicio_previsto=a["inicio_previsto"], fim_previsto=a["fim_previsto"],
        descricao=a["descricao"],
        validador=termos.Pessoa(a["validador_nome"], a["validador_matricula"]),
        inicio=a["inicio"], fim=a["fim"],
        tecnico=termos.Pessoa(a["tecnico_nome"], a["tecnico_matricula"]), obs=a["obs"])
    try:
        odt, pdf, erro_pdf = termos.gerar_demanda(t)
    except Exception as e:
        return Resultado(f"❌ Não consegui gerar o termo de demanda: {e}", ok=False)
    if pdf is None:
        return Resultado(f"⚠️ **Termo de demanda do {a['chamado']} gerado só em ODT** — "
                         f"o PDF falhou ({erro_pdf}).", arquivos=[str(odt)])
    return Resultado(f"✅ **Termo de demanda do {a['chamado']} gerado.**",
                     arquivos=[str(pdf), str(odt)])


# Catálogo deste arquivo (o __init__ junta todos, na ordem de _ORDEM).
FERRAMENTAS: list[Ferramenta] = [
    Ferramenta(
        "gerar_termo",
        "TROCA DE MÁQUINA: gera o Termo de Responsabilidade de Instalação "
        "(com/sem backup) em PDF. Não é o termo de evento (gerar_termo_demanda). "
        "Nome, matrícula e unidade o sistema lê do chamado; dos equipamentos basta "
        "o tombo, o resto ele busca no Itom.",
        {"type": "object", "properties": {
            "chamado": {"type": "string"},
            "backup": {"type": "boolean", "description":
                       "true = COM backup e restore. Só se o técnico disser: nunca deduza."},
            "maquinas": {"type": "array", "items": {"type": "object", "properties": {
                "saiu": _EQUIP_ESQUEMA,
                "entrou": _EQUIP_ESQUEMA,
            }}},
            "nome": {"type": "string", "description":
                     "Nome do USUÁRIO (pessoa), só se o técnico disser. "
                     "Nome da máquina vai em maquinas[].hostname."},
            "matricula": {"type": "string", "description": "Só se o técnico disser."},
            "unidade": {"type": "string", "description": "Só se o técnico disser."},
            "onedrive": {"type": "boolean", "description": "Com backup: oferecido pelo OneDrive?"},
            "observacoes": {"type": "string"},
        }, "required": ["maquinas"]},
        preparar=_prep_termo, executar=_exec_termo, antes=_antes_termo,
        # Com o chamado, lê mesmo sem as máquinas: a que saiu vem dele (30/10).
        # Sem chamado, lê só o Itom (máquinas ditas).
        precisa_ler=lambda a: isinstance(a.get("backup"), bool)
        and bool(str(a.get("chamado") or "").strip() or a.get("maquinas")),
        dominio="termos",
    ),
    Ferramenta(
        "gerar_termo_demanda",
        "EVENTO / TAREFA DE DEMANDA: gera a comprovação de prestação de serviço "
        "(validador assina). Solicitante, local, horário previsto e descrição do "
        "evento o sistema lê do chamado.",
        {"type": "object", "properties": {
            "chamado": {"type": "string"},
            "validador_nome": {"type": "string", "description": "Quem valida/assina no evento."},
            "validador_matricula": {"type": "string"},
            "inicio": {"type": "string", "description": "hh:mm em que o técnico começou de fato."},
            "fim": {"type": "string", "description": "hh:mm em que terminou de fato."},
            "obs": {"type": "string", "description": "O que o técnico fez, nas palavras dele."},
            "local": {"type": "string", "description":
                      "Onde é o evento: o que o técnico disse ou o que o Pedido do chamado diz."},
            "descricao": {"type": "string", "description": "Só se o técnico corrigir."},
            "validador_a_mao": {"type": "boolean", "description":
                                "true só se o técnico disser que o validador fica em branco."},
        }, "required": ["chamado"]},
        preparar=_prep_demanda, executar=_exec_demanda, antes=_antes_demanda,
        # Lê já na 1ª chamada (23/10): a pergunta do validador leva o Pedido,
        # para a IA tirar dele o local. A ficha fica guardada para a 2ª.
        precisa_ler=lambda a: bool(str(a.get("chamado") or "").strip()),
        dominio="termos",
    ),
]
