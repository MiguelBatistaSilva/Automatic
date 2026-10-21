# Atribuição Interna

- Ações → Atribuição Interna: passa o chamado para uma FILA (Departamento de
  Serviço), com ou sem técnico. Não mexe no relógio do SLA →
  atribuir_chamado.
- Os técnicos chamam de: atribuir, encaminhar, escalonar, passar para a fila
  X, mandar para o fulano, puxar/pegar o chamado para mim.
- Qual texto (modo):
  - puxar (o MAIS usado): o técnico pega o chamado para resolver ele mesmo
    (para_mim) → "Prezado(a), Informo que sua solicitação encontra-se em
    análise…".
  - contato: pegou para si e JÁ falou com o usuário → "Contato com êxito,
    suporte realizando intervenção técnica."
  - escalonar: o técnico não conseguiu resolver e passa para outra fila ou
    outro técnico → "Encaminhando para análise. Atividades realizadas:
    <motivo>". O motivo é obrigatório: se ele não disse, pergunte.
  - livre: o técnico ditou um texto próprio.
- O sistema monta o texto; passe só o modo e o motivo/texto.
- Passe a fila e o técnico como o técnico DISSE (ex.: "iguatu", "Gabriel"):
  o sistema acha o nome exato no Assyst. Se o técnico atende mais de uma
  fila, o sistema decide ou devolve a pergunta. Não invente a fila.
