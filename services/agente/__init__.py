"""
services/agente — O Assistente do Automatic (protótipo, 2026-09-29).

O modelo de linguagem só INTERPRETA o pedido do técnico e escolhe uma
ferramenta com parâmetros; quem executa são os mesmos serviços que o bot já
usa (bot/services/*), sem nenhum arquivo de fluxo alterado. Toda ação que
ESCREVE no Assyst passa por um cartão de confirmação na tela antes de rodar.

  llm.py          cliente HTTP da Groq (API compatível com a da OpenAI)
  ferramentas.py  catálogo: esquema para o modelo, validação, cartão, execução
  assistente.py   a conversa: histórico -> texto OU ação a confirmar

Não importa reflex: a página (state/assistente_state.py) é só quem chama.
"""
