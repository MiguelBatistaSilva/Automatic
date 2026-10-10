"""
services/agente/cartao.py — Regras do CARTÃO do plano, iguais em qualquer tela.

Saiu de state/assistente_state.py em 10/10 para o bot do Telegram usar as
MESMAS regras do chat do app: quais botões o cartão mostra (pelo checkpoint
de cada passo) e as notas que voltam para a IA no histórico. Quem desenha
(Reflex ou Telegram) só traduz os códigos em botões da sua tela.
"""

# código -> rótulo do botão
ROTULOS = {
    "confirmar": "Confirmar",
    "retomar": "Retomar",
    "do_zero": "Refazer do zero",
    "simular": "Simular (não salva)",
    "cancelar": "Cancelar",
}

# Botão do cartão -> desfecho no registro dos pedidos.
DESFECHO = {"confirmar": "confirmou", "simular": "simulou",
            "retomar": "retomou", "do_zero": "refez"}


def botoes(acoes) -> tuple[list[str], str]:
    """(códigos dos botões, aviso) do cartão, pelo checkpoint de cada passo
    (mesmas regras dos diálogos da página de Desmembramento e do início da
    Requisição)."""
    multi = len(acoes) > 1
    avisos = [(f"{a.titulo}: " if multi else "") + a.aviso for a in acoes if a.aviso]

    if any(a.checkpoint == "corrompido" for a in acoes):
        return ["cancelar"], (
            "O checkpoint de um passo existe mas está ilegível. Não vou rodar: "
            "poderia recriar chamados que já existem.")

    def e_req(a):
        return a.ferramenta == "criar_requisicoes"

    pendente = [a for a in acoes if a.checkpoint == "pendente"]
    concluido_desm = [a for a in acoes if a.checkpoint == "concluido" and not e_req(a)]
    concluido_req = [a for a in acoes if a.checkpoint == "concluido" and e_req(a)]

    cods: list[str] = []
    if not multi and concluido_req:
        cods = []  # lote já criado: só dá para fechar o cartão
    elif pendente:
        cods = ["retomar"]
        if any(not e_req(a) for a in pendente) or concluido_desm:
            cods.append("do_zero")
    elif concluido_desm:
        # Sozinho, "Confirmar" não faria nada (já concluído); num plano, roda
        # os outros passos e esse só relata.
        cods = (["confirmar"] if multi else []) + ["do_zero"]
    else:
        cods = ["confirmar"]

    escreve = any(a.escreve for a in acoes)
    if escreve and cods and all(a.pode_simular or not a.escreve for a in acoes):
        cods.append("simular")
    cods.append("cancelar")
    if pendente and any(not e_req(a) for a in pendente):
        avisos.insert(0, "Existe uma execução pela metade.")
    if concluido_desm:
        avisos.insert(0, "Já foi concluído antes.")
    return cods, " ".join(avisos)


def usa_assyst(acoes) -> bool:
    """False = plano só com passos locais (ex.: gerar termo): sem login."""
    return any(getattr(a, "assyst", True) for a in acoes)


def nota_plano(acoes, escreve: bool) -> str:
    """O que fica no histórico da IA quando o plano vira cartão."""
    nomes = ", ".join(a.titulo for a in acoes)
    return (f"[Mostrei o plano ({nomes}) para o técnico confirmar.]" if escreve
            else f"[Executando: {nomes}.]")


def nota_lembrar(lembrar: list[str]) -> str:
    """Consultas que valem para o resto da conversa (de quem é o chamado)."""
    return "".join(f"\n[Já consultado: {l}]" for l in lembrar)


def nota_fim(acoes, resultados: list[tuple[str, bool, str]], erro_geral: str = "") -> str:
    """Nota curta para a IA de como o plano terminou — sem nada lido do
    Assyst (LGPD). `resultados` = (título, ok, texto) de cada passo que rodou."""
    if erro_geral:
        return f"[O plano não rodou: {erro_geral}]"
    feitos = ", ".join(f"{t} ({'ok' if ok else 'falhou'})" for t, ok, _ in resultados)
    pulados = len(acoes) - len(resultados)
    return (f"[Plano executado: {feitos}"
            + (f"; {pulados} passo(s) não rodaram por causa da falha" if pulados else "")
            + ". O resultado foi mostrado ao técnico.]")
