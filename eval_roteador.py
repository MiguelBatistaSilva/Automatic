"""
eval_roteador.py — Prova com gabarito do ROTEADOR do Assistente (08/10).

Confere, para pedidos de exemplo, se services/agente/roteador.py escolhe o
domínio certo. NÃO chama a IA nem o Assyst: roda em menos de 1 s e não gasta
tokens. Rodar a cada mudança no roteador, em domínio novo (ex.: documentos)
ou quando um pedido real cair no domínio errado — esse pedido vira um caso.

Uso:
    python eval_roteador.py          (sai com código 1 se algum caso falhar)

Critério de cada caso:
  - esperado = conjunto de domínios: TODOS precisam ter sido escolhidos.
    Domínio A MAIS é só AVISO: gasta um pouco mais de tokens, mas a IA
    continua com a ferramenta certa.
  - esperado = None ("não sei"): o roteador TEM que mandar tudo. Escolher um
    domínio aqui é erro — a IA ficaria sem as outras ferramentas.
  - esperado = NAO_FILAS: qualquer coisa, menos o domínio de filas (pedidos
    que falam de fila mas não são para configurar).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.agente.roteador import dominios

NAO_FILAS = "nao_filas"

C, R, F = "chamados", "requisicao", "filas"

# (conversa, esperado). Conversa = texto (um pedido) ou lista de mensagens
# alternando técnico/assistente, começando pelo técnico.
CASOS = [
    # --- filas (configurar_filas) ---
    ("Configure a fila 2N CATI Sistemas no Assyst", {F}),
    ("configura as filas 2N CATI FCB e 2N CATI Remoto", {F}),
    ("cria a fila 2N CATI TJ pra mim", {F}),
    ("preciso adicionar a fila 2N CATI Demais Capital no meu Assyst", {F}),
    ("monta minhas filas: 2N CATI FCB, 2N CATI Remoto", {F}),
    ("quero a fila 2N CATI Sistemas no Assyst", {F}),
    ("configure o Assyst pra mostrar a fila 2N CATI TJ", {F}),
    ("cadastra o perfil de coluna", {F}),
    ("faz a configuração da fila 2N CATI Remoto", {F}),
    # achados em 08/10 (caíam em "não sei"):
    ("coloca a fila 2N CATI Sistemas no meu menu", {F}),
    ("preciso das filas 2N CATI FCB e Remoto configuradas", {F}),
    # --- chamados ---
    ("resolva o R2479463, instalação feita", {C}),
    ("o chamado da Carla, coloca aguardando fornecedor", {C}),
    ("qual o SLA do S2477461?", {C}),
    ("mostra minha fila", {C}),
    ("inicia o atendimento do R2479463", {C}),
    ("programa o R2479463 pra amanhã às 14h, o usuário está em reunião", {C}),
    ("aplica a base de impressora no R2479463", {C}),
    ("retoma o R2479463, o usuário respondeu", {C}),
    ("coloca o S2477461 aguardando o usuário, troquei o teclado", {C}),
    ("adiciona a informação 'aguardando peça' no R2479463", {C}),
    ("o chamado do João está estourado?", {C}),
    ("quantos chamados tem na fila do FCB?", {C}),
    # "tombos" puxa também requisição: aviso esperado (só gasta um pouco mais).
    ("desmembra o R2479463 nos tombos 265287 e 333284", {C}),
    ("fecha o R2479463, troquei o cabo", {C}),
    ("finaliza o chamado do Pedro", {C}),
    ("encerra o S2477461", {C}),
    ("pausa o R2479463 esperando peça da Positivo", {C}),
    ("R2479463: impressora instalada", {C}),
    ("qual o prazo da Maria?", {C}),
    # --- requisição ---
    ("abre requisição pros tombos 265287 e 333284, matrícula 5244", {R}),
    ("cria uma requisição de serviço para a matrícula 905245 no edifício FCB", {R}),
    ("preciso de requisições pro patrimônio FCBVCUSTO265287", {R}),
    # --- mais de um domínio no mesmo pedido ---
    ("resolve o R2479463 e configura a fila 2N CATI Sistemas", {C, F}),
    ("abre requisição pro tombo 265287 e depois resolve o R2479463", {C, R}),
    # --- não reconhecidos: tem que mandar tudo ---
    ("oi, tudo bem?", None),
    ("obrigado!", None),
    ("sim", None),
    ("o que você sabe fazer?", None),
    # --- fala de fila, mas NÃO é configurar ---
    ("a fila 2N CATI Sistemas está cheia hoje", NAO_FILAS),
    ("quem está na fila do FCB hoje?", NAO_FILAS),
    # --- conversa: a resposta curta herda o domínio do pedido ---
    (["configure a fila 2N CATI Sistemas no Assyst", "Confirma o nome?", "sim"], {F}),
    (["resolve o chamado da Carla", "Achei 2. Qual?", "o primeiro"], {C}),
    (["oi", "Olá! Em que posso ajudar?", "abre requisição pro tombo 265287"], {R}),
]


def _historico(conversa) -> list[dict]:
    if isinstance(conversa, str):
        conversa = [conversa]
    papeis = ("user", "assistant")
    return [{"role": papeis[i % 2], "content": t} for i, t in enumerate(conversa)]


def _avaliar(escolhido, esperado) -> tuple[str, str]:
    """('ok' | 'aviso' | 'erro', detalhe)."""
    if esperado is None:
        return ("ok", "") if escolhido is None else ("erro", "devia mandar tudo")
    if esperado == NAO_FILAS:
        return ("erro", "caiu em filas") if escolhido and F in escolhido else ("ok", "")
    if escolhido is None:
        return "erro", "não reconheceu (mandou tudo)"
    faltam = esperado - escolhido
    if faltam:
        return "erro", f"faltou {sorted(faltam)}"
    extras = escolhido - esperado
    return ("aviso", f"a mais {sorted(extras)}") if extras else ("ok", "")


def main() -> int:
    contagem = {"ok": 0, "aviso": 0, "erro": 0}
    for conversa, esperado in CASOS:
        escolhido = dominios(_historico(conversa))
        situacao, detalhe = _avaliar(escolhido, esperado)
        contagem[situacao] += 1
        if situacao != "ok":
            pedido = conversa if isinstance(conversa, str) else " / ".join(conversa)
            marca = "❌" if situacao == "erro" else "⚠️"
            print(f"{marca} {pedido!r}\n     escolheu {escolhido}, esperado "
                  f"{esperado} — {detalhe}")
    total = len(CASOS)
    print(f"\n{contagem['ok']} de {total} certos · {contagem['aviso']} aviso(s) · "
          f"{contagem['erro']} erro(s)")
    return 1 if contagem["erro"] else 0


if __name__ == "__main__":
    sys.exit(main())
