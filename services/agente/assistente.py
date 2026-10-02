"""
services/agente/assistente.py — Um turno da conversa com o Assistente.

`responder(historico)` recebe a conversa (só mensagens de texto: 'user' e
'assistant') e devolve um `Resposta`: texto para mostrar e o PLANO (as
ações de navegador preparadas, na ordem) para o cartão.

As ferramentas LOCAIS (ex.: listar bases) rodam aqui mesmo e o resultado volta
ao modelo, que continua o raciocínio — até `_MAX_VOLTAS` idas e vindas.
As de NAVEGADOR nunca rodam aqui: viram cartão e quem executa é a página,
depois do clique (ou direto, se forem só leitura).

PLANO PASSO A PASSO (2026-10-01): o gpt-oss da Groq chama UMA ferramenta por
resposta (não manda várias de uma vez). Por isso, a cada ação preparada o
modelo recebe "preparada; se houver outra ação no pedido, chame agora" e vai
acrescentando passos até responder sem ferramenta — aí o plano está pronto.
"""

import dataclasses
import datetime
import json
import re

from services.agente import llm
from services.agente.ferramentas import FERRAMENTAS, Acao, esquemas

# Idas e vindas com o modelo num pedido: cada passo do plano gasta uma, e
# consultas locais (listar bases) outras. Cada uma custa ~1.000+ tokens do
# limite de 8.000/minuto do plano grátis.
_MAX_VOLTAS = 8

def _frase_final(achados: list[str], acoes: list[Acao]) -> str:
    """A frase acima do cartão, escrita pelo código (02/10): o que a
    investigação achou + o que vai ser feito. Ex.: 'O R2451960 está no prazo
    (RESTAM 2h10min). Vou aplicar a base X no R2451960 e resolver o R2451960.'"""
    from services.agente.ferramentas import frase_do_plano
    partes = []
    for a in achados:
        # Formato do _inv_verificar_sla: "R1: NO PRAZO — RESTAM 2h10min (fila X); R2: ..."
        for item in a.split("; "):
            m = re.match(r"(\S+): (NO PRAZO|ESTOURADO) — (.+?) \(fila", item)
            if m:
                # m[3] vem do sla_engine: "RESTAM 2h10min" / "ESTOURADO há 3h".
                tempo = re.sub(r"^(RESTAM|ESTOURADO)\s*", "", m[3]).strip()
                if m[2] == "NO PRAZO":
                    partes.append(f"O {m[1]} está no prazo (restam {tempo}).")
                else:
                    partes.append(f"O {m[1]} está estourado {tempo}.")
    return " ".join(partes + [frase_do_plano(acoes)]).strip()


def _preparada(pedido: str, acoes: list[Acao]) -> str:
    """Resposta da ferramenta quando a ação entra no plano. Repete o PEDIDO e
    o plano até aqui: sem isso o modelo às vezes anunciava duas ações e só
    preparava uma (visto em 01/10)."""
    plano = "; ".join(f"{i}) {a.titulo} {a.args.get('chamados', '')}".strip()
                      for i, a in enumerate(acoes, 1))
    return (
        f"Ação preparada. PEDIDO DO TÉCNICO: \"{pedido}\". PLANO ATÉ AQUI: {plano}. "
        "Compare: se o pedido tem alguma ação que NÃO está no plano, chame a "
        "ferramenta dela agora. Só quando TODAS estiverem no plano, responda com "
        "uma frase curta NO FUTURO dizendo o que vai ser feito depois que o "
        "técnico confirmar (ex.: 'Vou programar o R1 e colocar o R2 aguardando "
        "fornecedor.'), sem chamar ferramenta. Nada foi executado ainda."
    )

SISTEMA = """Você é o Assistente do Automatic, a ferramenta dos técnicos do CATI \
(TJCE) que automatiza o sistema de chamados Assyst. Responda em português do \
Brasil, curto e direto.

Regras:
- Para fazer qualquer coisa no Assyst, use uma ferramenta. Nunca diga que fez \
algo sem ter chamado a ferramenta.
- Não invente dados (números de chamado, tombos, textos, nomes de base). Se \
faltar algo obrigatório, pergunte ao técnico.
- Quando tiver os dados, chame a ferramenta direto: o técnico confirma num \
cartão na tela antes de qualquer alteração. Não peça confirmação por texto.
- Base de Conhecimento citada por um trecho (ex.: "a base de toner"): use listar_bases_conhecimento com esse trecho como filtro. Se sobrar uma só, use essa; se sobrarem várias, pergunte mostrando as opções.
- Desmembramento: se a descrição não tiver {{tombo}}, o sistema acrescenta o tombo no fim sozinho — não pergunte sobre isso.
- Se o pedido tiver VÁRIAS ações (ex.: programar um chamado e colocar outro \
aguardando fornecedor), chame UMA ferramenta para cada ação, todas na mesma \
resposta e na ordem pedida. Elas viram um plano único que o técnico confirma \
de uma vez e que roda em sequência; se um passo falhar, os seguintes não rodam.
- O resultado das execuções aparece direto na tela para o técnico; você não \
o recebe. Não tente adivinhar números de chamados criados.
- Se pedirem algo que nenhuma ferramenta cobre, diga que ainda não sabe fazer.

Investigação (ferramentas marcadas INVESTIGAÇÃO rodam na hora e o resultado \
volta para você):
- Os técnicos citam o chamado pelo NOME do usuário ("o chamado da Carla"). \
Nesse caso, use buscar_chamado_por_usuario antes de qualquer ação. Se vierem \
vários, pergunte qual (mostrando nome e setor).
- Antes de RESOLVER um chamado, use verificar_sla.
- Depois de investigar, conte em UMA linha o que encontrou antes de dizer o \
que vai fazer (ex.: "O chamado está no prazo (restam 2h10). Vou aplicar a \
base e resolver.").

"""


def _instrucoes() -> str:
    """Comportamento (SISTEMA) + o que ele SABE do CATI/Assyst (a base de
    conhecimento em services/agente/conhecimento/, lida a cada pedido) + a
    data de hoje."""
    from services.agente import conhecimento
    return (SISTEMA + "\n\n=== BASE DE CONHECIMENTO DO CATI ===\n\n"
            + conhecimento.texto() + "\n" + _hoje())


_DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
         "sexta-feira", "sábado", "domingo"]


def _hoje() -> str:
    """Data de hoje nas instruções, para 'amanhã'/'sexta' virarem dd/mm."""
    d = datetime.date.today()
    return f"\nHoje é {_DIAS[d.weekday()]}, {d:%d/%m/%Y}.\n"


@dataclasses.dataclass
class Resposta:
    texto: str = ""
    # O PLANO: as ações do pedido, na ordem em que vão rodar (vazio = só texto).
    acoes: list[Acao] = dataclasses.field(default_factory=list)


_AVISOS_INVESTIGA = {
    "buscar_chamado_por_usuario": "Procurando o chamado na sua fila...",
    "verificar_sla": "Verificando o SLA...",
}


def responder(historico: list[dict], matricula: str = "", senha: str = "",
              avisar=None, modelo_id: str = "") -> Resposta:
    """Um pedido pode virar VÁRIAS ações (2026-10-01) — viram um plano só,
    confirmado de uma vez e executado em fila na mesma sessão.

    Se a ÚLTIMA ferramenta pedida não pôde ser preparada (falta dado) e o
    modelo respondeu com uma pergunta, o plano é descartado: nada vira cartão
    pela metade — o técnico responde e o pedido é montado de novo inteiro.

    INVESTIGAÇÃO: ferramentas de leitura do Assyst rodam aqui mesmo, numa
    Sessao aberta só se alguma for pedida e fechada no fim do turno (por isso
    `responder` precisa rodar inteiro na MESMA thread — Playwright sync).
    `avisar(texto)` mostra na tela o que está sendo investigado.
    """
    from services.agente.sessao import ErroSessao, Sessao

    avisar = avisar or (lambda t: None)
    sessao = None
    msgs = [{"role": "system", "content": _instrucoes()}] + historico
    ferramentas = esquemas()
    pedido = next((h["content"] for h in reversed(historico)
                   if h["role"] == "user"), "")
    acoes: list[Acao] = []
    achados: list[str] = []   # resultados do verificar_sla (vão na frase final)
    faltou = False
    terminou = False          # o modelo marcou ultima_acao=true
    try:
        for _ in range(_MAX_VOLTAS):
            avisar("Pensando...")
            m = llm.conversar(msgs, ferramentas, modelo_id or llm.PADRAO)
            chamadas = m.get("tool_calls") or []
            texto = (m.get("content") or "").strip()
            if not chamadas:
                if acoes and not faltou:
                    return Resposta(texto=texto, acoes=acoes)
                return Resposta(texto=texto)

            msgs.append({"role": "assistant", "content": texto, "tool_calls": chamadas})
            faltou = False
            for c in chamadas:
                nome = c["function"]["name"]
                try:
                    args = json.loads(c["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                f = FERRAMENTAS.get(nome)
                if f is None:
                    saida, faltou = f"Ferramenta inexistente: {nome}.", True
                elif f.local:
                    saida = f.local(args)
                elif f.investiga:
                    if not matricula or not senha:
                        saida = ("Não dá para consultar o Assyst: credenciais não "
                                 "cadastradas (Opções -> Credenciais). Avise o técnico.")
                    else:
                        avisar(_AVISOS_INVESTIGA.get(nome, "Consultando o Assyst..."))
                        if sessao is None:
                            sessao = Sessao(matricula, senha, lambda m, t="info": None)
                        try:
                            saida = f.investiga(args, sessao)
                        except ErroSessao as e:
                            saida = f"Não consegui consultar o Assyst: {e}"
                        except Exception as e:
                            saida = f"Erro ao consultar o Assyst: {e}"
                else:
                    r = f.preparar(args)
                    if isinstance(r, str):
                        saida, faltou = r, True  # falta algo: o modelo pergunta
                    elif any(x.ferramenta == r.ferramenta and x.args == r.args for x in acoes):
                        # O modelo pediu de novo um passo que já está no plano
                        # (visto em 02/10: dois "Resolver" iguais). Não duplica.
                        saida = ("Essa ação JÁ ESTÁ no plano — não repita. "
                                 + _preparada(pedido, acoes))
                    else:
                        acoes.append(r)
                        saida = _preparada(pedido, acoes)
                        if args.get("ultima_acao") is True:
                            terminou = True
                if nome == "verificar_sla":
                    achados.append(saida)
                msgs.append({"role": "tool", "tool_call_id": c["id"], "content": saida})
            # O modelo marcou o último passo: plano pronto SEM mais uma ida à
            # IA só para a frase final (cortada em 02/10 — era a ida que
            # estourava o limite da Groq; ver ferramentas._com_ultima_acao).
            if terminou and acoes and not faltou:
                return Resposta(texto=_frase_final(achados, acoes), acoes=acoes)
        if acoes and not faltou:
            return Resposta(texto="", acoes=acoes)
        return Resposta(texto="Não consegui concluir o pedido. Pode reformular?")
    finally:
        if sessao is not None:
            sessao.fechar()
