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
from services.agente.ferramentas import (
    FERRAMENTAS, Acao, _lista, _lista_curta, esquemas, requisicoes_coladas,
)

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
- TEXTO QUE VAI PARA O CHAMADO (procedimentos do Resolver e do Aguardando \
Usuário, texto de Informação/Fornecedor, descrição do Desmembramento, motivo \
do Programar): use SÓ o que o técnico disse, apenas no formato pedido. Se ele \
não disse, pergunte (ex.: "Qual procedimento coloco na resolução?"). Aplicar \
uma base NÃO é procedimento: não escreva o texto a partir da base.
- Pergunte TUDO o que falta ANTES de chamar qualquer ferramenta do pedido — \
nunca prepare uma parte do pedido e pergunte o resto depois.
- Quando tiver os dados, chame a ferramenta direto: o técnico confirma num \
cartão na tela antes de qualquer alteração. Não peça confirmação por texto.
- Base de Conhecimento: passe o nome ou as palavras que o técnico disse; o \
sistema acha a cadastrada. Se ele devolver várias, pergunte qual.
- Se o pedido tiver VÁRIAS ações, chame UMA ferramenta para cada ação, na \
ordem pedida. Viram um plano único, confirmado de uma vez; se um passo \
falhar, os seguintes não rodam. Em cada ação, `ultima_acao` = true só na \
última do pedido.
- O resultado das execuções aparece direto na tela para o técnico; você não \
o recebe. Não tente adivinhar números de chamados criados.
- Se pedirem algo que nenhuma ferramenta cobre, diga que ainda não sabe fazer.
- Ferramentas de INVESTIGAÇÃO rodam na hora e o resultado volta para você. \
Depois de investigar, conte em UMA linha o que encontrou antes de dizer o \
que vai fazer (ex.: "O chamado está no prazo (restam 2h10). Vou aplicar a \
base e resolver.").
- As regras do CATI/Assyst (quando investigar, SLA, formatos) estão na BASE \
DE CONHECIMENTO abaixo: siga-as. Ela traz o assunto do pedido; se precisar \
de outro assunto do índice, use consultar_conhecimento.

"""


def _instrucoes(dominios: "set[str] | None" = None) -> str:
    """Comportamento (SISTEMA) + o que ele SABE do CATI/Assyst — só a parte
    da base dos `dominios` do pedido (None = inteira) e o ÍNDICE de todos os
    assuntos (o resto ele busca com consultar_conhecimento) + a data."""
    from services.agente import conhecimento
    return (SISTEMA + "\n\n=== BASE DE CONHECIMENTO DO CATI ===\n\n"
            + conhecimento.texto(dominios)
            + "\n\n=== ÍNDICE DE TODOS OS ASSUNTOS ===\n" + conhecimento.indice()
            + "\n" + _hoje())


# Resposta de quem não achou ferramenta para o pedido. Com o roteador ligado
# isso pode ser falta de ferramenta NO RECORTE (pedido mal classificado):
# aí refaz uma vez com tudo — ver `responder`.
_NAO_SABE = re.compile(r"n[ãa]o sei fazer|n[ãa]o (tenho|h[áa]) (uma |nenhuma )?ferramenta"
                       r"|n[ãa]o consigo fazer|ainda n[ãa]o (sei|consigo)", re.I)


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
    # O que o agente fez para chegar aqui (consultas, passos montados), no
    # passado — aparece no expansor da mensagem, como no Claude (06/10).
    atividade: list[str] = dataclasses.field(default_factory=list)
    # Uma linha resumindo a atividade (o rótulo do expansor).
    resumo: str = ""


def _alvo(args: dict) -> str:
    """'de Carla' / 'do S2477461' — o complemento do status vivo."""
    if args.get("nome"):
        return f" de {args['nome']}"
    chamados = _lista(args.get("chamados"))
    if chamados:
        return f" do {_lista_curta(chamados, 4)}" if len(chamados) == 1 \
            else f" dos chamados {_lista_curta(chamados, 4)}"
    return ""


def _status(nome: str, args: dict) -> tuple[str, str]:
    """(status vivo, linha de atividade) de uma consulta. O vivo no gerúndio
    ("Verificando o SLA do S2477461..."), a atividade no passado."""
    alvo = _alvo(args)
    if nome == "buscar_chamado_por_usuario":
        return f"Procurando o chamado{alvo} na sua fila...", f"Procurou o chamado{alvo} na fila"
    if nome == "verificar_sla":
        return f"Verificando o SLA{alvo}...", f"Verificou o SLA{alvo}"
    if nome == "listar_bases_conhecimento":
        filtro = f" ('{args['filtro']}')" if args.get("filtro") else ""
        return "Consultando as bases de conhecimento...", f"Consultou as bases de conhecimento{filtro}"
    if nome == "consultar_conhecimento":
        assunto = args.get("assunto") or ""
        return (f"Lendo o que sei sobre {assunto}...",
                f"Leu a base do Assistente ('{assunto}')")
    return "Consultando o Assyst...", f"Consultou o Assyst ({nome})"


def _curto(texto: str, limite: int = 160) -> str:
    texto = " ".join(str(texto).split())
    return texto if len(texto) <= limite else texto[:limite - 1] + "…"


def _resumo(consultas: int, acoes: list[Acao]) -> str:
    partes = []
    if consultas:
        partes.append(f"{consultas} consulta{'s' if consultas > 1 else ''}")
    if acoes:
        partes.append(f"{len(acoes)} passo{'s' if len(acoes) > 1 else ''} preparado"
                      + ("s" if len(acoes) > 1 else ""))
    return " · ".join(partes)


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
    from services.agente.roteador import dominios as rotear
    from services.agente.sessao import ErroSessao, Sessao

    avisar = avisar or (lambda t: None)
    sessao = None
    # Só as ferramentas e a base do domínio do pedido (roteador, 07/10).
    doms = rotear(historico)
    msgs = [{"role": "system", "content": _instrucoes(doms)}] + historico
    ferramentas = esquemas(doms)
    pedido = next((h["content"] for h in reversed(historico)
                   if h["role"] == "user"), "")
    # Lista de requisições colada (botão "Copiar lista" do cartão): vira o
    # cartão direto, sem a IA — ela reescreveria o lote (ver requisicoes_coladas).
    colada = requisicoes_coladas(pedido)
    if colada is not None:
        return Resposta(texto="Montei o cartão com a lista exatamente como você colou.",
                        acoes=[colada],
                        atividade=["Reconheceu a lista colada — o cartão saiu dela, sem a IA"])
    acoes: list[Acao] = []
    achados: list[str] = []   # resultados do verificar_sla (vão na frase final)
    atividade: list[str] = []
    consultas = 0
    faltou = False
    terminou = False          # o modelo marcou ultima_acao=true

    def resposta(texto: str, com_acoes: bool = True) -> Resposta:
        a = acoes if com_acoes else []
        return Resposta(texto=texto, acoes=a, atividade=atividade,
                        resumo=_resumo(consultas, a))

    try:
        for volta in range(_MAX_VOLTAS):
            avisar("Pensando..." if volta == 0 else "Decidindo o próximo passo...")
            m = llm.conversar(msgs, ferramentas, modelo_id or llm.PADRAO)
            chamadas = m.get("tool_calls") or []
            texto = (m.get("content") or "").strip()
            if not chamadas and doms is not None and not acoes and _NAO_SABE.search(texto):
                # Rede de segurança do roteador: "não sei fazer" com as
                # ferramentas RECORTADAS pode ser só classificação errada.
                # Refaz UMA vez com todas — o roteador nunca pode bloquear.
                doms = None
                msgs[0] = {"role": "system", "content": _instrucoes()}
                ferramentas = esquemas()
                atividade.append("Não achou no assunto do pedido — procurou em todas as ferramentas")
                continue
            if not chamadas:
                # Terminou PERGUNTANDO: o pedido está incompleto. Descarta o
                # que já foi preparado — cartão pela metade (ex.: só a base,
                # sem o Resolver) pode ser confirmado por engano (06/10).
                pergunta = texto.rstrip().endswith("?")
                return resposta(texto, com_acoes=bool(acoes) and not faltou and not pergunta)

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
                    vivo, feito = _status(nome, args)
                    avisar(vivo)
                    saida = f.local(args)
                    consultas += 1
                    atividade.append(feito)
                elif f.investiga:
                    if not matricula or not senha:
                        saida = ("Não dá para consultar o Assyst: credenciais não "
                                 "cadastradas (Opções -> Credenciais). Avise o técnico.")
                        atividade.append("Não consultou o Assyst: credenciais não cadastradas")
                    else:
                        vivo, feito = _status(nome, args)
                        if sessao is None:
                            # O login só acontece na 1ª consulta (Sessao.pagina),
                            # e leva ~6 s: o status diz isso.
                            vivo = f"Entrando no Assyst e {vivo[0].lower()}{vivo[1:]}"
                            sessao = Sessao(matricula, senha, lambda m, t="info": None)
                        avisar(vivo)
                        try:
                            saida = f.investiga(args, sessao)
                        except ErroSessao as e:
                            saida = f"Não consegui consultar o Assyst: {e}"
                        except Exception as e:
                            saida = f"Erro ao consultar o Assyst: {e}"
                        consultas += 1
                        atividade.append(f"{feito} — {_curto(saida)}")
                else:
                    r = f.preparar(args)
                    if isinstance(r, str):
                        saida, faltou = r, True  # falta algo: o modelo pergunta
                        atividade.append(f"Faltou informação para {f.nome.replace('_', ' ')}"
                                         f" — {_curto(r, 120)}")
                    elif any(x.ferramenta == r.ferramenta and x.args == r.args for x in acoes):
                        # O modelo pediu de novo um passo que já está no plano
                        # (visto em 02/10: dois "Resolver" iguais). Não duplica.
                        saida = ("Essa ação JÁ ESTÁ no plano — não repita. "
                                 + _preparada(pedido, acoes))
                    else:
                        acoes.append(r)
                        avisar(f"Montando o passo: {r.titulo}...")
                        atividade.append(f"Preparou o passo: {r.titulo}")
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
                return resposta(_frase_final(achados, acoes))
        if acoes and not faltou:
            return resposta("")
        return resposta("Não consegui concluir o pedido. Pode reformular?", com_acoes=False)
    finally:
        if sessao is not None:
            sessao.fechar()
