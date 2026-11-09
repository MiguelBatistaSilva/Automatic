"""
services/agente/ferramentas/bases.py — Bases de Conhecimento e Desmembramento.

Achar a base pelo nome (exato ou pelas palavras), consultar a base de
conhecimento do Assistente, desmembrar (Criar + Base / Só Criar) e aplicar
base (Só Base). Os fluxos são as mesmas classes da página de Desmembramento.
"""

import difflib
import re

from services.agente.ferramentas.base import (
    Acao,
    ChameDeNovo,
    Ferramenta,
    _CHAMADOS,
    _lista,
    _lista_curta,
    _ok_falha,
    _sem_acento,
)
from services.agente.ferramentas.verificacoes import (
    _EDIFICIO_DITO,
    _antes_corrigir,
    _com_correcoes,
    _executar_correcoes,
)
from services.agente.sessao import Resultado, Sessao


# --------------------------------------------------------------------------- #
# Bases de Conhecimento — nome da base
# --------------------------------------------------------------------------- #

def _nomes_bases() -> list[str]:
    from services.dados import kb_store
    return [e["nome_artigo"] for e in kb_store.carregar()]


# Palavras que não ajudam a achar a base ("a BASE DE teste DO patch cord").
_PALAVRAS_VAZIAS = {"a", "o", "as", "os", "de", "da", "do", "das", "dos", "e",
                    "em", "na", "no", "para", "com", "bc", "base", "via"}


def _palavras(texto: str) -> list[str]:
    return [p for p in re.findall(r"\w+", _sem_acento(texto or ""))
            if p not in _PALAVRAS_VAZIAS]


def _bases_por_palavras(trecho: str) -> list[str]:
    """Bases cujo nome tem TODAS as palavras do trecho, em qualquer ordem e
    sem acento (06/10): "teste de patch cord" acha "BC - Teste de Cabo Patch
    Cord" — a busca pelo trecho inteiro não achava, por causa do "Cabo"."""
    alvo = _palavras(trecho)
    if not alvo:
        return []
    # Início de palavra: "monitor" acha "Monitores", "instal" acha "Instalação".
    return [n for n in _nomes_bases()
            if all(any(w.startswith(p) for w in _palavras(n)) for p in alvo)]


# Vai junto de toda dúvida sobre base (08/10): num pedido com DUAS bases
# ("a do Itom e a da Nomenclatura") a IA consultou só a primeira e INVENTOU
# nomes para a segunda ("BC - Nomenclatura de Equipamentos", que não existe).
_SO_NOMES_REAIS = (" ANTES de perguntar: se o pedido cita OUTRAS bases, chame "
                   "aplicar_base para cada uma também, e pergunte tudo de uma vez. "
                   "Cite SÓ nomes de base que vieram das ferramentas — nunca invente "
                   "exemplos.")


def _resolver_base(nome: str) -> tuple[str, str]:
    """(nome_exato, erro). Aceita o nome exato (sem diferença de maiúsculas)
    ou, desde 06/10, a ÚNICA base que tem todas as palavras citadas — o nome
    escolhido aparece no cartão antes de confirmar. Mais de uma: pergunta.
    Nunca escolhe por semelhança (base errada não tem desfazer)."""
    nomes = _nomes_bases()
    alvo = (nome or "").strip().lower()
    for n in nomes:
        if n.lower() == alvo:
            return n, ""
    por_palavras = _bases_por_palavras(nome)
    if len(por_palavras) == 1:
        return por_palavras[0], ""
    if len(por_palavras) > 1:
        return "", (f"Mais de uma base tem '{nome}': {', '.join(por_palavras[:10])}. "
                    "Pergunte ao técnico qual delas." + _SO_NOMES_REAIS)
    parecidas = difflib.get_close_matches(nome or "", nomes, n=8, cutoff=0.3)
    parecidas += [n for n in nomes if alvo and alvo in n.lower() and n not in parecidas]
    if parecidas:
        return "", ("Base de Conhecimento não encontrada: "
                    f"'{nome}'. Parecidas: {', '.join(parecidas[:10])}. "
                    "Pergunte ao técnico qual delas." + _SO_NOMES_REAIS)
    return "", (f"Base de Conhecimento não encontrada: '{nome}'. Use "
                "listar_bases_conhecimento para ver as cadastradas." + _SO_NOMES_REAIS)


# --------------------------------------------------------------------------- #
# Bases de Conhecimento (local)
# --------------------------------------------------------------------------- #

def _local_conhecimento(args: dict) -> str:
    """Um assunto da base de conhecimento — para o que está FORA do domínio
    do pedido (o do domínio já vem nas instruções)."""
    from services.agente import conhecimento
    return conhecimento.ler(args.get("assunto") or "")


def _desc_conhecimento() -> str:
    from services.agente import conhecimento
    return ("Lê um assunto da base de conhecimento do CATI (regras, nomes, "
            "como fazer). Use quando o pedido precisar de um assunto que não "
            "está nas instruções. Assuntos:\n" + conhecimento.indice())


def _local_bases(args: dict) -> str:
    nomes = _nomes_bases()
    filtro = (args.get("filtro") or "").strip()
    if filtro:
        nomes = _bases_por_palavras(filtro)
    if not nomes:
        return "Nenhuma base encontrada."
    return "Bases cadastradas: " + "; ".join(nomes[:80])


# --------------------------------------------------------------------------- #
# Desmembramento — Criar + Base / Só Criar
# --------------------------------------------------------------------------- #

MARCADOR_TOMBO = "{{tombo}}"
# O marcador como a IA escreve: {tombo} (o formato da Requisição), {{tombo}},
# { tombo }... Tudo vira o MARCADOR_TOMBO do fluxo (09/11: a IA escreveu
# {tombo} e ele iria literal para os 7 filhos no Assyst).
_MARCADOR_SOLTO = re.compile(r"\{+\s*tombo\s*\}+", re.I)


def _prep_desmembrar(args: dict) -> "Acao | str":
    from bot.services import desmembramento_service as ds

    pai = str(args.get("chamado_pai") or "").strip()
    tombos = _lista(args.get("tombos"))
    descricao = (args.get("descricao") or "").strip()
    if not pai:
        return "Falta o número do chamado pai. Pergunte ao técnico."
    pedido = str(args.get("_pedido") or "")
    conferido = args.get("conferido") is True
    sem_equipamento = bool(args.get("_sem_equipamento"))
    ctx = f' Pedido do chamado: "{pedido}"' if pedido else ""
    if not tombos:
        if sem_equipamento:
            return ("O chamado não cita equipamento nem tombo: não parece caso de "
                    "desmembrar. Avise o técnico e pergunte se quer mesmo; se ele "
                    f"insistir, peça os tombos.{ctx}")
        if args.get("_lido_do_chamado"):
            return ("A descrição do chamado não traz tombos. Pergunte ao técnico os "
                    f"tombos (um filho por tombo).{ctx}")
        return "Falta a lista de tombos (um filho por tombo). Pergunte ao técnico."
    # Gabarito do técnico (03/11): 1 tombo é questionado, e obedecido se confirmar.
    if len(tombos) == 1 and not conferido:
        return (f"Só 1 tombo ({tombos[0]}): desmembrar costuma ser para vários. Diga "
                "ao técnico que é 1 tombo e pergunte se quer desmembrar mesmo; só com "
                f"o sim dele chame de novo com conferido=true.{ctx}")
    # A IA só escreve a descrição dos filhos depois de VER o Pedido: no turno
    # seguinte à análise ela não o tem mais e inventava (04/11, eval_agente.py).
    if pedido and not (descricao and args.get("_refeita")):
        # Com base, a IA tirava a descrição do NOME da base ("Instalação de
        # computador.") em vez do Pedido (09/11, S2510350).
        da_base = (f' A base ("{args["base"]}") é aplicada à parte: NÃO use o nome '
                   "dela na descrição." if args.get("base") else "")
        return ChameDeNovo(
            "Preencha `descricao` dos filhos: o serviço do Pedido abaixo, curto e "
            "formal, sem local nem nomes (se o técnico ditou a descrição, mantenha a "
            f'dele).{da_base} Tombos: {", ".join(tombos)}.{ctx}')
    if not descricao:
        return ("Falta a descrição dos chamados filhos. Pergunte ao técnico "
                "qual texto usar.")
    descricao = _MARCADOR_SOLTO.sub(MARCADOR_TOMBO, descricao)
    if re.search(r"[{}]", descricao.replace(MARCADOR_TOMBO, "")):
        # Chave que sobrou iria literal para todos os filhos no Assyst.
        return ("A descrição tem chaves que não são o marcador do tombo: "
                f'"{descricao}". Reescreva sem chaves, com {MARCADOR_TOMBO} '
                "onde entra o tombo (ou sem ele, e o sistema põe no fim).")
    if MARCADOR_TOMBO not in descricao:
        descricao = f"{descricao} Tombo: {MARCADOR_TOMBO}"

    base = ""
    if args.get("base"):
        base, erro = _resolver_base(args["base"])
        if erro:
            return erro

    sit = ds.situacao(pai)
    linhas = [
        f"**Modo:** {'Criar + Base' if base else 'Só Criar'}",
        f"**Chamado pai:** {pai}",
        f"**Filhos:** {len(tombos)} (tombos {_lista_curta(tombos)})",
    ]
    if base:
        linhas.append(f"**Base:** {base}")
    linhas.append(f"**Descrição (1º filho):** {descricao.replace(MARCADOR_TOMBO, tombos[0])}")
    avisos = []
    if sem_equipamento:
        avisos.append("O chamado não cita equipamento: confira se é para desmembrar mesmo.")
    do_chamado = _lista(args.get("_tombos_do_chamado"))
    if do_chamado and set(do_chamado) != set(tombos):
        avisos.append("Tombos diferentes dos que estão na descrição do chamado "
                      f"({_lista_curta(do_chamado)}).")
    if sit.get("resumo"):
        avisos.append(sit["resumo"])
    return Acao(
        ferramenta="desmembrar",
        args={"chamado_pai": pai, "tombos": tombos, "descricao": descricao, "base": base},
        titulo="Desmembramento",
        linhas=linhas,
        escreve=True,
        checkpoint=sit["estado"],
        aviso=" ".join(avisos),
    )


def _precisa_ler_desmembrar(args: dict) -> bool:
    """Sempre que souber o pai (04/11): só a ficha diz se os tombos batem e se o
    chamado tem equipamento. Lida uma vez por conversa (ver ficha._VALIDADE)."""
    return bool(str(args.get("chamado_pai") or "").strip())


def _antes_desmembrar(args: dict, s: Sessao) -> dict:
    from services.agente import triagem
    from services.agente.ficha import ler_ficha

    f = ler_ficha(s.pagina, str(args.get("chamado_pai") or ""), s.log)
    if f is None:
        return args
    pedido = f.pedido
    out = {**args, "_lido_do_chamado": True, "_pedido": pedido, "_tombos_do_chamado": f.tombos,
           "_sem_equipamento": not (f.tombos or triagem.tombo_do_item_b(f.item_b)
                                    or triagem.equipamentos(pedido)
                                    or triagem.tipo_do_pedido(pedido) == "desmontagem/mudança")}
    if not _lista(args.get("tombos")) and f.tombos:
        out["tombos"] = f.tombos
    return out


def _kb_config(nome_base: str) -> dict:
    from services.dados import kb_store
    e = next(e for e in kb_store.carregar() if e["nome_artigo"] == nome_base)
    return {"keyword": e["keyword"], "nome_artigo": e["nome_artigo"]}


def _exec_desmembrar(a: dict, s: Sessao) -> Resultado:
    """As mesmas classes que a página de Desmembramento usa, na página da
    sessão do plano. O login delas vê a sessão ativa e segue."""
    import pandas as pd
    from services.dados import checkpoint
    from services.fluxos.flow_desmembramento_pw import FluxoCompletoPW, FluxoCriarPW
    from services.fluxos.kb_manager_pw import executar_kb_unica_pw

    pai, tombos = a["chamado_pai"], a["tombos"]
    df = pd.DataFrame([[t] for t in tombos], columns=["tombo"])
    page = s.pagina()
    if a["base"]:
        kb = _kb_config(a["base"])
        FluxoCompletoPW(page, s.matricula, s.senha, s.log, origem="ui").executar(
            df=df, descricao_base=a["descricao"], numero_chamado=pai,
            kb_function=lambda p, l: executar_kb_unica_pw(p, l, kb, voltar_ao_evento=True),
            iniciar_do_zero=s.iniciar_do_zero)
    else:
        FluxoCriarPW(page, s.matricula, s.senha, s.log, origem="ui").executar(
            df=df, descricao_base=a["descricao"], numero_chamado=pai,
            iniciar_do_zero=s.iniciar_do_zero)

    # O fluxo não devolve nada: o relato sai do checkpoint (como no bot).
    estados = {l["index"]: l for l in checkpoint.status_linhas(pai)}
    feitos = 0
    linhas = []
    for i, tombo in enumerate(tombos):
        l = estados.get(i, {})
        feito = l.get("status") == "concluido"
        feitos += feito
        extra = "" if feito else f" ({l.get('status', 'pendente')})"
        linhas.append(f"- {_ok_falha(feito)} tombo {tombo} → **{l.get('numero_filho') or '—'}**{extra}")
    cab = f"**Desmembramento de {pai}** — {feitos} de {len(tombos)} concluído(s)."
    return Resultado("\n".join([cab] + linhas), ok=feitos == len(tombos))


# --------------------------------------------------------------------------- #
# Desmembramento — Só Base
# --------------------------------------------------------------------------- #

def _prep_aplicar_base(args: dict) -> "Acao | str":
    from bot.services import desmembramento_service as ds

    chamados = _lista(args.get("chamados"))
    if not chamados:
        return "Falta a lista de chamados onde aplicar a base."
    if not args.get("base"):
        return "Falta o nome da Base de Conhecimento."
    base, erro = _resolver_base(args["base"])
    if erro:
        return erro
    sit = ds.situacao(ds.chave_bc(chamados))
    return _com_correcoes(Acao(
        ferramenta="aplicar_base",
        args={"chamados": chamados, "base": base},
        titulo="Aplicar Base (Só Base)",
        linhas=[f"**Base:** {base}",
                f"**Chamados:** {len(chamados)} ({_lista_curta(chamados)})"],
        escreve=True,
        checkpoint=sit["estado"],
        aviso=sit.get("resumo", ""),
    ), args, "aplicar a base")


def _exec_aplicar_base(a: dict, s: Sessao) -> Resultado:
    from services.dados import checkpoint
    from services.fluxos.flow_desmembramento_pw import FluxoBCPW, _chave_checkpoint
    from services.fluxos.kb_manager_pw import executar_kb_unica_pw

    # Corrige antes (30/10). Aqui a falha não segura a base (ela não fecha o
    # chamado): só vai para o resultado.
    correcoes = _executar_correcoes(a, s)
    kb = _kb_config(a["base"])
    FluxoBCPW(s.pagina(), s.matricula, s.senha, s.log, origem="ui").executar(
        filhos=a["chamados"],
        kb_function=lambda p, l: executar_kb_unica_pw(p, l, kb, voltar_ao_evento=False),
        iniciar_do_zero=s.iniciar_do_zero)
    por_indice = {l["index"]: l["status"]
                  for l in checkpoint.status_linhas(_chave_checkpoint(a["chamados"]))}
    feitos = 0
    linhas = []
    for i, c in enumerate(a["chamados"]):
        st = por_indice.get(i, "pendente")
        feitos += st == "concluido"
        linhas.append(f"- {_ok_falha(st == 'concluido')} {c}" + ("" if st == "concluido" else f" ({st})"))
    linhas += [f"- {_ok_falha(ok)} Correção {n} — {txt}" for n, (ok, txt) in correcoes.items()]
    cab = f"**Base {a['base']}** — {feitos} de {len(a['chamados'])} chamado(s)."
    return Resultado("\n".join([cab] + linhas), ok=feitos == len(a["chamados"]))


# Catálogo deste arquivo (o __init__ junta todos, na ordem de _ORDEM).
FERRAMENTAS: list[Ferramenta] = [
    Ferramenta(
        "consultar_conhecimento",
        _desc_conhecimento,  # montada na hora: o índice dos assuntos
        {"type": "object", "properties": {
            "assunto": {"type": "string", "description": "Chave do índice (ex.: chamados/sla)."},
        }, "required": ["assunto"]},
        preparar=lambda a: "", local=_local_conhecimento,
        dominio="geral",
    ),
    Ferramenta(
        "listar_bases_conhecimento",
        "Lista as Bases de Conhecimento cadastradas (filtro: palavras do nome).",
        {"type": "object", "properties": {"filtro": {"type": "string"}}},
        preparar=lambda a: "", local=_local_bases,
        dominio="chamados",
    ),
    Ferramenta(
        "desmembrar",
        "Cria um chamado filho por tombo a partir do pai; com 'base', aplica a "
        "base em cada filho. Com o número do pai, chame JÁ, sem perguntar nada: o "
        "sistema lê os tombos do chamado e diz o que faltar.",
        {"type": "object", "properties": {
            "chamado_pai": {"type": "string"},
            "tombos": {"type": "array", "items": {"type": "string"}, "description":
                       "Os que o técnico disse; sem eles, o sistema lê do chamado."},
            "descricao": {"type": "string", "description":
                          "Dos filhos. Só se o técnico ditou; senão o sistema devolve o "
                          "Pedido para você escrever. {{tombo}} onde entra o tombo."},
            "conferido": {"type": "boolean", "description":
                          "true só depois que o técnico disse sim à pergunta do sistema."},
            "base": {"type": "string", "description":
                     "Só se o técnico pediu uma base: nome ou palavras dela."},
        }, "required": ["chamado_pai"]},
        preparar=_prep_desmembrar, executar=_exec_desmembrar,
        # Tombos e descrição que faltarem vêm da ficha do pai (23/10).
        antes=_antes_desmembrar, precisa_ler=_precisa_ler_desmembrar,
        dominio="chamados",
    ),
    Ferramenta(
        "aplicar_base",
        "Aplica uma Base de Conhecimento em chamados que já existem. Uma chamada "
        "por base.",
        {"type": "object", "properties": {
            "chamados": _CHAMADOS,
            "base": {"type": "string", "description":
                     "As palavras que o técnico disse (ex.: 'memória'); o sistema acha "
                     "a base ou devolve as opções. Não peça o nome completo antes."},
            "edificio": _EDIFICIO_DITO,
        }, "required": ["chamados", "base"]},
        preparar=_prep_aplicar_base, executar=_exec_aplicar_base, antes=_antes_corrigir,
        dominio="chamados",
    ),
]
