"""
services/agente/ferramentas/verificacoes.py — O que o código confere no
chamado ANTES de resolver, aplicar base ou desmembrar (30/10).

Correção de Edifício/Item B pela triagem e relógio pausado (pares de
retomada). Usado por várias ferramentas e pelo agendados.py.
"""

import datetime

from services.agente.ferramentas.base import _lista
from services.agente.sessao import Sessao

# --------------------------------------------------------------------------- #
# Correção do chamado (30/10) — Edifício e Item B antes de resolver/aplicar base
# --------------------------------------------------------------------------- #
#
# O técnico pede "aplica a base e resolve" sem olhar o chamado: o `antes`
# lê a ficha, roda a triagem (services/agente/triagem.py) e o cartão já sai
# com o que corrigir. Correção certa entra no cartão; dúvida (seção ambígua,
# palpite pela cidade) volta à IA como pergunta, e a resposta vem em
# `edificio`. O fluxo é o flow_corrigir_chamado_pw.

_EDIFICIO_DITO = {"type": "string", "description":
                  "Só quando o sistema perguntar o Edifício: o que o técnico escolheu."}


def _antes_corrigir(args: dict, s: Sessao) -> dict:
    from services.agente.ficha import ler_ficha
    from services.agente.triagem import IC_NAO_LOCALIZADO, triar_ficha
    from services.dados import referencia

    dito = str(args.get("edificio") or "").strip()
    correcoes, linhas, pendencias = {}, [], []
    for numero in (c.strip().upper() for c in _lista(args.get("chamados"))):
        f = ler_ficha(s.pagina, numero, s.log)
        if f is None:
            linhas.append(f"{numero}: não consegui abrir para conferir Edifício e Item B")
            continue
        t = triar_ficha(f)
        c, partes = {}, []
        e, b = t.edificio, t.item_b
        if e.por_definir:
            if dito:
                c["edificio"] = referencia.conferir("edificio", dito).valor or dito
                partes.append(f"Edifício '{e.atual or 'vazio'}' → {c['edificio']} (dito pelo técnico)")
            elif e.sugerido and "confirme" not in e.motivo:
                c["edificio"] = e.sugerido
                partes.append(f"Edifício '{e.atual or 'vazio'}' → {e.sugerido} ({e.motivo})")
            elif e.sugerido:
                pendencias.append(f"{numero}: Edifício '{e.atual or 'vazio'}'; pela cidade seria "
                                  f"{e.sugerido}. Peça a confirmação e mande em edificio.")
            elif e.opcoes:
                pendencias.append(f"{numero}: Edifício '{e.atual or 'vazio'}'; opções: "
                                  f"{' | '.join(e.opcoes)}. Pergunte qual e mande em edificio.")
            else:
                pendencias.append(f"{numero}: Edifício '{e.atual or 'vazio'}' e a seção não tem "
                                  "histórico. Pergunte o edifício e mande em edificio.")
        # Só corrige Item B vazio ou IC NÃO LOCALIZADO: um item de verdade
        # foi escolhido por alguém.
        if b.sugerido and (not b.atual.strip() or b.atual.strip() == IC_NAO_LOCALIZADO) \
                and b.sugerido != b.atual.strip():
            c["item_b"] = b.sugerido
            partes.append(f"Item B '{b.atual or 'vazio'}' → {b.sugerido}; {b.motivo}")
        if c:
            correcoes[numero] = c
            linhas.append(f"{numero}: " + " · ".join(partes))
    return {**args, "_lido_do_chamado": True, "_correcoes": correcoes,
            "_linhas_correcao": linhas, "_pendencias": pendencias}


def _pergunta_edificio(args: dict, verbo: str) -> str:
    return (f"Antes de {verbo}, o Edifício precisa ser definido:\n- "
            + "\n- ".join(args["_pendencias"])
            + "\nPergunte ao técnico (tudo de uma vez) e chame de novo com edificio.")


def _com_correcoes(r: "Acao | str", args: dict, verbo: str) -> "Acao | str":
    """Junta ao cartão o que o `antes` achou. Dúvida no Edifício = pergunta."""
    if isinstance(r, str) or not args.get("_lido_do_chamado"):
        return r
    if args.get("_pendencias"):
        return _pergunta_edificio(args, verbo)
    r.args["correcoes"] = args.get("_correcoes") or {}
    if args.get("_linhas_correcao"):
        r.linhas.insert(1, "**Corrigir antes:**\n" + "\n".join(f"- {l}" for l in args["_linhas_correcao"]))
    return r


def _executar_correcoes(a: dict, s: Sessao) -> dict[str, tuple[bool, str]]:
    """Corrige os chamados do cartão. {numero: (ok, texto para o resultado)}."""
    from services.agente.ficha import esquecer
    from services.fluxos.flow_corrigir_chamado_pw import corrigir_chamado

    saida = {}
    for numero, c in (a.get("correcoes") or {}).items():
        s.log(f"Corrigindo o chamado {numero}...", "status")
        try:
            ok, info = corrigir_chamado(s.pagina(), s.log, numero, c.get("edificio", ""),
                                        c.get("item_b", ""), s.modo_teste)
        except Exception as e:
            ok, info = False, {"erro": str(e), "mudou": {}}
        esquecer(numero)
        mudou = "; ".join(f"{k}: {d}" for k, (_, d) in info.get("mudou", {}).items())
        saida[numero] = (ok, (mudou or "já estava certo") if ok
                         else f"correção falhou: {info.get('erro')}")
    return saida


# --------------------------------------------------------------------------- #
# Relógio pausado antes de resolver (30/10)
# --------------------------------------------------------------------------- #
#
# Chamado pausado (ex.: Atendimento Programado) NÃO tem "Resolvido" no menu
# Ações — só o par da pausa (visto no S2503433). O `antes` do resolver lê o
# histórico; pausado = a IA pergunta se retoma. Os pares sem texto do técnico
# o Assistente faz; Fornecedor/Gestor pedem texto, então só avisa.

_PAR_DA_PAUSA = {
    "Atendimento Programado": "Atendimento Iniciado",
    "Aguardando Info do Usuário *": "Info Recebidas do Usuário *",
    "Aguardando Info do Fornecedor": "Info Recebida do Fornecedor",
    "Aguardando Info do Gestor": "Info Recebidas do Gestor",
}
_RETOMA_SOZINHO = {"Atendimento Programado", "Aguardando Info do Usuário *"}


def _pausa_atual(historico: list[dict]) -> "tuple[str, str] | None":
    """(pausa, data) se a última ação de relógio for uma pausa."""
    from services.regras.sla_engine import TIPOS_FIM, TIPOS_RETOMADA

    relogio = []
    for h in historico:
        tipo = h.get("tipo", "")
        if tipo in _PAR_DA_PAUSA or tipo in TIPOS_RETOMADA or tipo in TIPOS_FIM or tipo == "Reabrir":
            try:
                relogio.append((datetime.datetime.strptime(h["data"], "%d/%m/%y %H:%M"), tipo, h["data"]))
            except (KeyError, ValueError):
                continue
    if not relogio:
        return None
    # Mesmo minuto: o histórico vem do mais novo para o mais antigo, e o max
    # fica com o primeiro empatado.
    _, tipo, data = max(relogio, key=lambda r: r[0])
    return (tipo, data) if tipo in _PAR_DA_PAUSA else None


def _antes_resolver(args: dict, s: Sessao) -> dict:
    from services.fluxos.flow_sla_pw import extrair_historico_chamado

    args = _antes_corrigir(args, s)
    pausados = {}
    for numero in (c.strip().upper() for c in _lista(args.get("chamados"))):
        p = _pausa_atual(extrair_historico_chamado(s.pagina(), numero, s.log) or [])
        if p:
            pausados[numero] = p
    return {**args, "_pausados": pausados}


def _retomada(args: dict) -> "str | dict | None":
    """Pergunta (str), {numero: pausa} a retomar antes, ou None."""
    pausados = args.get("_pausados") or {}
    if not pausados:
        return None
    texto = "; ".join(f"{n} está em '{t}' desde {d}" for n, (t, d) in pausados.items())
    manuais = {n: t for n, (t, _) in pausados.items() if t not in _RETOMA_SOZINHO}
    if manuais:
        return (f"Não dá para resolver ainda: {texto}. O Assyst só oferece 'Resolvido' "
                "depois da retomada, e essa ('" + "', '".join(_PAR_DA_PAUSA[t] for t in manuais.values())
                + "') precisa de um texto do técnico: pergunte o que foi recebido e use "
                "info_recebida_fornecedor (Gestor: ele retoma no Assyst). Depois, resolver.")
    if not args.get("retomar"):
        pares = ", ".join(sorted({_PAR_DA_PAUSA[t] for t, _ in pausados.values()}))
        return (f"Pausado: {texto}. O Assyst só oferece 'Resolvido' depois de retomar "
                f"('{pares}'). Pergunte ao técnico se retoma agora (o sistema faz) e chame "
                "de novo com retomar=true — ou ele retoma pelo Reflex (Iniciar Atendimento).")
    return {n: t for n, (t, _) in pausados.items()}


def _executar_retomadas(a: dict, s: Sessao) -> dict[str, tuple[bool, str]]:
    from services.agente.ficha import esquecer
    from services.fluxos.flow_atendimento_pw import iniciar_atendimento
    from services.fluxos.flow_info_recebida_pw import info_recebida_usuario

    saida = {}
    for numero, pausa in (a.get("retomar") or {}).items():
        s.log(f"Retomando o chamado {numero} ({_PAR_DA_PAUSA[pausa]})...", "status")
        try:
            if pausa == "Atendimento Programado":
                ok = iniciar_atendimento(s.pagina(), s.log, numero, modo_teste=s.modo_teste)
            else:
                ok, _ = info_recebida_usuario(s.pagina(), s.log, numero, modo_teste=s.modo_teste)
        except Exception as e:
            ok = False
            s.log(f"Falha ao retomar {numero}: {e}", "error")
        esquecer(numero)
        saida[numero] = (bool(ok), _PAR_DA_PAUSA[pausa])
    return saida
