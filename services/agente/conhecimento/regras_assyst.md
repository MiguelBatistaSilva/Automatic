# Regras do Assyst e do CATI

## Ações no chamado
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

## SLA
- Chamado com SLA ESTOURADO NÃO pode ser resolvido. Avise o técnico ("o
  chamado está estourado e não pode ser resolvido") e ofereça colocá-lo em
  Aguardando Info do Usuário com os mesmos procedimentos. Só prepare essa
  ação se o técnico concordar.
- Antes de RESOLVER um chamado, verifique o SLA (verificar_sla).
- Se o técnico não disser a fila do SLA, use 2N CATI FCB.

## Como os técnicos pedem
- Os técnicos costumam citar o chamado pelo NOME do usuário ("o chamado da
  Carla") e não pelo número. Nesse caso, procure o chamado na fila do
  técnico (buscar_chamado_por_usuario) antes de qualquer ação. Se vierem
  vários, pergunte qual (mostrando nome e setor).

## Procedimentos (Resolver e Aguardando Info do Usuário)
- Só o que o técnico disse que foi feito; se ele não disse, pergunte.
- Um procedimento só: uma frase simples, sem traço
  ("Instalação realizada com sucesso.").
- Vários: um por linha, começando com "- ", no particípio, ";" no fim e o
  último com "." ("- Atualizado o antivírus;" / "- Reiniciada a máquina.").
- Observação (ex.: pendente de teste): no fim, depois de uma linha em branco.

## Requisição de Serviço
- Matrícula do usuário afetado, edifício, fila e técnico atribuído são o
  que o técnico costuma informar. Se faltar algum, pergunte.
- Tombo: são os 6 últimos dígitos do código da máquina
  (FCBVCUSTO265287 → 265287). O sistema faz esse corte sozinho.
- Uma requisição por tombo. O tombo vai na descrição e no Item B (com `*`).
- Resumo: "Requisição de Serviço". Categoria: quase sempre "Configuração".
