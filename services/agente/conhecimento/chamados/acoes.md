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
