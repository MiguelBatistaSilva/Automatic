"""
services/agente/ferramentas/investigacao.py — Só leitura.

As investigações (o resultado volta para a IA decidir o próximo passo:
achar o chamado pelo nome, SLA, triagem, máquina no Itom) e a consulta
que vai direto para a tela (SLA). Nada aqui grava no Assyst.
12/11: busca e análise POR FILA (flow_minhafila_pw.FILAS_ASSYST): o técnico
diz a fila ("analisa a minha fila", "o chamado do Marcos na fila Demais
Capital"); sem fila, a busca olha a Minha Fila e depois a 2N CATI FCB.
consultar_minha_fila (cartão "Minha Fila") saiu em 10/11.
"""

from services.agente.ferramentas import base
from services.agente.ferramentas.base import (
    Acao,
    Ferramenta,
    _CHAMADOS,
    _FILA,
    _lista,
    _sem_acento,
)
from services.agente.sessao import Resultado, Sessao
from services.regras.sla_engine import FILAS, FILA_PADRAO


# --------------------------------------------------------------------------- #
# Só leitura — SLA
# --------------------------------------------------------------------------- #

def _prep_sla(args: dict) -> "Acao | str":
    chamados = _lista(args.get("chamados"))
    if not chamados:
        return "Falta a lista de chamados para analisar."
    fila = args.get("fila") or FILA_PADRAO
    if fila not in FILAS:
        return f"Fila desconhecida: '{fila}'. Filas válidas: {', '.join(FILAS)}."
    return Acao(ferramenta="analisar_sla", args={"chamados": chamados, "fila": fila},
                titulo="Análise de SLA", linhas=[], escreve=False)


def _exec_sla(a, s: Sessao) -> Resultado:
    """Analisa o SLA de cada chamado, na página da sessão."""
    from services.assyst.browser_pw import _usuario_afetado_pw
    from services.fluxos.flow_sla_pw import extrair_historico_chamado
    from services.regras.sla_engine import calcular_sla

    page = s.pagina()
    linhas = [f"**SLA — fila {a['fila']}**"]
    todos_ok = True
    for numero in a["chamados"]:
        s.log(f"Analisando o SLA de {numero}...", "status")
        historico = extrair_historico_chamado(page, numero, s.log)
        if historico is None:
            todos_ok = False
            linhas.append(f"- ❌ {numero} — não consegui abrir o chamado ou ler o histórico")
            continue
        _usuario_afetado_pw(page)  # garante a tela do chamado (como no bot)
        r = calcular_sla(historico, a["fila"])
        icone = "🔴" if r.get("estourado") else "🟢"
        linhas.append(f"- {icone} **{numero}** — {r.get('mensagem', '--')} "
                      f"(gasto {r.get('tempo_gasto_str', '--')}, resta "
                      f"{r.get('tempo_restante_str', '--')})")
    return Resultado("\n".join(linhas), ok=todos_ok)


# --------------------------------------------------------------------------- #
# Investigação — leituras cujo resultado volta para a IA (2026-10-01)
# --------------------------------------------------------------------------- #

def _tecnico_logado(page) -> str:
    try:
        return page.locator("#userDropDownButton_label").first.inner_text(timeout=2000).strip()
    except Exception:
        return ""


# Sem fila dita, a busca pelo nome olha estas, nesta ordem (12/11).
_FILAS_DA_BUSCA = ("Minha Fila", "2N CATI FCB")
_FILA_ASSYST = {"type": "string", "description":
                "Fila do Assyst que o técnico disse: 'Minha Fila' ou o nome da "
                "fila (ex.: 2N CATI FCB, 2N CATI TJ, 2N CATI Demais Capital)."}


def _fila_pedida(args: dict) -> tuple[str, str]:
    """(nome da fila em FILAS_ASSYST ou '', erro para a IA ou '')."""
    from services.fluxos.flow_minhafila_pw import FILAS_ASSYST, resolver_fila
    dita = str(args.get("fila") or "").strip()
    if not dita:
        return "", ""
    nome = resolver_fila(dita)
    if nome:
        return nome, ""
    return "", (f"Ainda não sei ler a fila '{dita}'. Filas que eu leio: "
                + ", ".join(FILAS_ASSYST) + ". Diga isso ao técnico.")


def _com_quem(c: dict, eu: str) -> str:
    """' (com Fulano: OUTRO técnico)', ' (sem técnico)' ou '' se é do logado."""
    t = (c.get("tecnico") or "").strip()
    if not t:
        return " (sem técnico atribuído)"
    a, b = _sem_acento(t), _sem_acento(eu)
    if b and (a in b or b in a):
        return ""
    return f" (com {t}: OUTRO técnico)"


def _inv_buscar_chamado(args: dict, s: Sessao) -> str:
    """Acha o chamado pelo NOME do usuário (e setor) — os técnicos lembram de
    "o chamado da Carla", não do número. Na fila que ele disse (12/11) ou, sem
    fila, na Minha Fila e depois na 2N CATI FCB. A comparação é feita aqui no
    código; para a IA só vão os chamados que BATEM com o nome que o próprio
    técnico citou, nunca a fila inteira. Chamado com outro técnico: a IA só
    avisa e segue (decisão dele, 10/11)."""
    from services.fluxos.flow_minhafila_pw import MINHA_FILA, ler_fila

    nome = _sem_acento(args.get("nome") or "").strip()
    setor = _sem_acento(args.get("setor") or "").strip()
    if not nome:
        return "Falta o nome do usuário para procurar."
    fila_dita, erro = _fila_pedida(args)
    if erro:
        return erro
    page = s.pagina()
    eu = _tecnico_logado(page)
    lidas, batem, onde = [], [], ""
    for nome_fila in ([fila_dita] if fila_dita else _FILAS_DA_BUSCA):
        fila = ler_fila(page, s.log, nome_fila)
        if fila is None:
            lidas.append(f"{nome_fila} (não carregou)")
            continue
        lidas.append(f"{nome_fila} ({len(fila)} chamados)")
        batem = [c for c in fila
                 if all(p in _sem_acento(c.get("afetado", "")) for p in nome.split())
                 and (not setor or all(p in _sem_acento(c.get("secao", "")) for p in setor.split()))]
        if batem:
            onde = nome_fila
            break
    if not batem:
        return (f"Nenhum chamado de '{args.get('nome')}' em: " + "; ".join(lidas)
                + ". Pergunte o número do chamado ou em que fila ele está.")
    linhas = [f"{c['referencia']} — {c.get('afetado', '')} ({c.get('secao', '')})"
              + ("" if onde == MINHA_FILA else _com_quem(c, eu)) for c in batem]
    if any("OUTRO técnico" in l for l in linhas):
        linhas[-1] += (". Se algum está com OUTRO técnico, avise o técnico disso "
                       "numa frase e siga (não pergunte por isso)")
    na = f" na fila {onde}"
    if len(batem) == 1:
        return f"Encontrado 1 chamado{na}: " + linhas[0]
    # "Todos os chamados do Fulano" (22/10): lote, sem perguntar — o cartão
    # mostra a lista para o técnico confirmar.
    if args.get("todos"):
        nomes = {_sem_acento(c.get("afetado", "")) for c in batem}
        aviso = ("" if len(nomes) == 1 else
                 " ATENÇÃO: são pessoas diferentes com esse nome; pergunte se são todas.")
        return (f"{len(batem)} chamados de '{args.get('nome')}'{na} (use TODOS no "
                f"próximo passo): " + "; ".join(linhas) + "." + aviso)
    return (f"{len(batem)} chamados batem com '{args.get('nome')}'{na}: " + "; ".join(linhas)
            + ". Pergunte ao técnico qual (mostre nome e setor).")


def _inv_verificar_sla(args: dict, s: Sessao) -> str:
    """SLA para a IA DECIDIR: só número, fila e tempo — nada do usuário."""
    from services.fluxos.flow_sla_pw import extrair_historico_chamado
    from services.regras.sla_engine import calcular_sla

    chamados = _lista(args.get("chamados"))
    if not chamados:
        return "Falta o número do chamado."
    fila = args.get("fila") or FILA_PADRAO
    if fila not in FILAS:
        return f"Fila desconhecida: '{fila}'. Filas válidas: {', '.join(FILAS)}."
    saida = []
    for numero in chamados:
        historico = extrair_historico_chamado(s.pagina(), numero, s.log)
        if historico is None:
            saida.append(f"{numero}: não consegui ler o histórico")
            continue
        r = calcular_sla(historico, fila)
        situacao = "ESTOURADO" if r.get("estourado") else "NO PRAZO"
        saida.append(f"{numero}: {situacao} — {r.get('mensagem', '')} (fila {fila})")
    return "; ".join(saida)


# --------------------------------------------------------------------------- #
# Triagem do chamado (22/10) — o Assistente olhando como técnico
# --------------------------------------------------------------------------- #
#
# Regras em services/agente/triagem.py. A DESCRIÇÃO é lida pelo código; a IA recebe
# seção, edifício, Item B, os tombos e o PEDIDO sem o bloco de dados pessoais
# (triagem.pedido_seguro) — para propor o desmembramento sem perguntar.

_MAX_TRIAGEM = 15   # ~5 s por chamado: a conversa não pode ficar presa


def _inv_consultar_maquina(args: dict, s: Sessao) -> str:
    """Série, hostname e ficha da máquina pelo tombo, no Itom (30/10). Dado
    de máquina, sem dado pessoal: volta à IA."""
    tombos = _lista(args.get("tombos"))
    if not tombos:
        return "Falta o tombo."
    achados = base._itom(tombos, s)
    if not achados:
        return "Não consegui entrar no Itom."
    linhas = []
    for t in tombos:
        m = achados.get(t)
        linhas.append(m.resumo() + (f" (outros hosts: {', '.join(m.outras)})" if m.outras else "")
                      if m else f"Tombo {t}: não está no Itom (sem agente ou tombo errado).")
    return "\n".join(linhas)


def _inv_analisar_chamado(args: dict, s: Sessao) -> str:
    from services.agente.ficha import ler_ficha
    from services.agente.triagem import triar_ficha

    chamados = _lista(args.get("chamados"))
    page, saida = s.pagina(), []
    fila_dita, erro = _fila_pedida(args)
    if erro:
        return erro
    if fila_dita and not chamados:
        # "Analisa a minha fila" / "a fila do 2N CATI FCB" (12/11): lê a fila
        # AQUI — para a IA vão só os números (os nomes ficam no código).
        from services.fluxos.flow_minhafila_pw import ler_fila
        fila = ler_fila(page, s.log, fila_dita)
        if fila is None:
            return f"Não consegui ler a fila {fila_dita} (a tela não carregou)."
        if not fila:
            return f"A fila {fila_dita} está VAZIA: não há chamado para analisar."
        chamados = [c["referencia"] for c in fila if c.get("referencia")]
        saida.append(f"Fila {fila_dita}: {len(chamados)} chamado(s).")
    if not chamados:
        return ("Falta o chamado. Pergunte qual chamado, de quem (aí use "
                "buscar_chamado_por_usuario) ou qual fila.")
    if len(chamados) > _MAX_TRIAGEM:
        saida.append(f"{len(chamados)} chamados; analisados os {_MAX_TRIAGEM} primeiros.")
        chamados = chamados[:_MAX_TRIAGEM]
    for numero in (c.strip().upper() for c in chamados):
        # Relê (recente=False): o técnico pode ter acabado de corrigir algo.
        f = ler_ficha(lambda: page, numero, s.log, recente=False)
        if f is None:
            saida.append(f"{numero}: não consegui abrir o chamado")
            continue
        saida.append(triar_ficha(f).resumo())
    return "\n".join(saida)


# Catálogo deste arquivo (o __init__ junta todos, na ordem de _ORDEM).
FERRAMENTAS: list[Ferramenta] = [
    Ferramenta(
        "buscar_chamado_por_usuario",
        "INVESTIGAÇÃO: acha o chamado pelo nome do usuário afetado, na fila "
        "que o técnico disse (sem fila: Minha Fila e depois 2N CATI FCB).",
        {"type": "object", "properties": {
            "nome": {"type": "string"},
            "setor": {"type": "string"},
            "fila": _FILA_ASSYST,
            "todos": {"type": "boolean", "description":
                      "true se o técnico disse TODOS os chamados dessa pessoa."},
        }, "required": ["nome"]},
        preparar=lambda a: "", investiga=_inv_buscar_chamado,
        dominio=("chamados", "termos"),
    ),
    Ferramenta(
        "verificar_sla",
        "INVESTIGAÇÃO: diz se o chamado está NO PRAZO ou ESTOURADO e quanto resta.",
        {"type": "object", "properties": {
            "chamados": _CHAMADOS,
            "fila": _FILA,
        }, "required": ["chamados"]},
        preparar=lambda a: "", investiga=_inv_verificar_sla,
        dominio="chamados",
    ),
    Ferramenta(
        "analisar_chamado",
        "INVESTIGAÇÃO (triagem): confere Edifício e Item B do chamado e diz o "
        "que corrigir (só leitura).",
        {"type": "object", "properties": {
            "chamados": _CHAMADOS,
            "fila": {**_FILA_ASSYST, "description": _FILA_ASSYST["description"]
                     + " Só quando o técnico pede para analisar a FILA, sem chamado."},
        }},
        preparar=lambda a: "", investiga=_inv_analisar_chamado,
        dominio="chamados",
    ),
    Ferramenta(
        "consultar_maquina",
        "INVESTIGAÇÃO: nº de série, hostname, IP e configuração da máquina pelo "
        "tombo, no Itom (só leitura). Termo e despacho já buscam a série sozinhos.",
        {"type": "object", "properties": {
            "tombos": {"type": "array", "items": {"type": "string"}},
        }, "required": ["tombos"]},
        preparar=lambda a: "", investiga=_inv_consultar_maquina,
        dominio=("chamados", "termos", "requisicao"),
    ),
    Ferramenta(
        "analisar_sla",
        "Mostra ao técnico o SLA (gasto/restante) dos chamados (só leitura).",
        {"type": "object", "properties": {
            "chamados": _CHAMADOS,
            "fila": _FILA,
        }, "required": ["chamados"]},
        preparar=_prep_sla, executar=_exec_sla,
        dominio="chamados",
    ),
]
