"""
services/agente/assistente.py — Um turno da conversa com o Assistente.

`responder(historico)` recebe a conversa (só mensagens de texto: 'user' e
'assistant') e devolve um `Resposta`: texto para mostrar e, se o modelo
pediu uma ferramenta de navegador, a `Acao` pronta para o cartão.

As ferramentas LOCAIS (ex.: listar bases) rodam aqui mesmo e o resultado volta
ao modelo, que continua o raciocínio — até `_MAX_VOLTAS` idas e vindas.
As de NAVEGADOR nunca rodam aqui: viram cartão e quem executa é a página,
depois do clique (ou direto, se forem só leitura).
"""

import dataclasses
import json

from services.agente import llm
from services.agente.ferramentas import FERRAMENTAS, Acao, esquemas

_MAX_VOLTAS = 4

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
- Uma ação por vez. Se pedirem duas, faça a primeira e diga que a outra vem \
em seguida.
- O resultado das execuções aparece direto na tela para o técnico; você não \
o recebe. Não tente adivinhar números de chamados criados.
- Se pedirem algo que nenhuma ferramenta cobre, diga que ainda não sabe fazer.
"""


@dataclasses.dataclass
class Resposta:
    texto: str = ""
    acao: Acao | None = None


def responder(historico: list[dict]) -> Resposta:
    msgs = [{"role": "system", "content": SISTEMA}] + historico
    ferramentas = esquemas()
    for _ in range(_MAX_VOLTAS):
        m = llm.conversar(msgs, ferramentas)
        chamadas = m.get("tool_calls") or []
        texto = (m.get("content") or "").strip()
        if not chamadas:
            return Resposta(texto=texto)

        msgs.append({"role": "assistant", "content": texto, "tool_calls": chamadas})
        acao = None
        for c in chamadas:
            nome = c["function"]["name"]
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            f = FERRAMENTAS.get(nome)
            if f is None:
                saida = f"Ferramenta inexistente: {nome}."
            elif f.local:
                saida = f.local(args)
            elif acao is not None:
                saida = "Só uma ação por vez: esta fica para depois."
            else:
                r = f.preparar(args)
                if isinstance(r, str):
                    saida = r  # falta algo: o modelo pergunta ao técnico
                else:
                    acao = r
                    saida = "Ação apresentada ao técnico para confirmação."
            msgs.append({"role": "tool", "tool_call_id": c["id"], "content": saida})
        if acao is not None:
            return Resposta(texto=texto, acao=acao)
    return Resposta(texto="Não consegui concluir o pedido. Pode reformular?")
