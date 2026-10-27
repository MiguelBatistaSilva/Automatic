# Ações no chamado

- Toda ação no chamado passa pelo menu Ações e abre um pop-up onde vai o
  texto padrão da auditoria. O sistema monta esse texto; o Assistente só
  passa os dados (chamado, procedimentos, dia/hora, motivo).
- Resolver = Ações → Resolvido. O texto da resolução é o mesmo modelo do
  Aguardando Info do Usuário, com "Testado pelo usuário? (X) Sim".

## Ações de relógio (pausa e retomada)
- Cada pausa tem a SUA retomada; o chamado volta sempre pelo par da ação
  que o pausou:
  - Aguardando Info do Usuário → info_recebida_usuario
  - Aguardando Info do Fornecedor → info_recebida_fornecedor
  - Programar Atendimento → iniciar_atendimento
- Se o técnico pedir para "retomar" sem dizer como o chamado foi pausado,
  pergunte (usuário, fornecedor ou atendimento programado).

## Despacho ao Serviço de Operações
- "Condenar um teclado", "mandar a máquina para a Operação / Serviço de
  Operações": o chamado vai pausado pela MESMA ação Aguardando Info do
  Fornecedor, mas com o script de despacho → despachar_operacao (não
  aguardar_fornecedor). O sistema monta o script.
- Precisa: chamado, tipo, localização do equipamento, marca, modelo e nº de
  série; tombo só para computador, notebook, monitor e impressora (teclado,
  mouse, webcam e caixa de som não têm).
- Testes realizados e defeito: vêm dos MODELOS POR DEFEITO da equipe. Pelo
  problema que o técnico contou ("scroll travando", "não liga"), escolha o
  modelo em defeito_modelo; nunca invente testes. Se ele não contou o
  defeito, o sistema diz o que perguntar.
- Fornecedor com texto livre continua sendo aguardar_fornecedor.
- Para retomar, o par é o mesmo: info_recebida_fornecedor.
