# Regras do Assyst e do CATI

## Ações no chamado
- Toda ação no chamado passa pelo menu Ações e abre um pop-up onde vai o
  texto padrão da auditoria. O sistema monta esse texto; o Assistente só
  passa os dados (chamado, procedimentos, dia/hora, motivo).
- Resolver = Ações → Resolvido. O texto da resolução é o mesmo modelo do
  Aguardando Info do Usuário, com "Testado pelo usuário? (X) Sim".

## SLA
- Chamado com SLA ESTOURADO NÃO pode ser resolvido. Avise o técnico ("o
  chamado está estourado e não pode ser resolvido") e ofereça colocá-lo em
  Aguardando Info do Usuário com os mesmos procedimentos. Só prepare essa
  ação se o técnico concordar.
- Antes de RESOLVER um chamado, verifique o SLA.
- Se o técnico não disser a fila do SLA, use 2N CATI FCB.

## Como os técnicos pedem
- Os técnicos costumam citar o chamado pelo NOME do usuário ("o chamado da
  Carla") e não pelo número. Nesse caso, procure o chamado na fila do
  técnico antes de qualquer ação. Se vierem vários, pergunte qual
  (mostrando nome e setor).
- Procedimentos ditos de forma solta ("atualizei o antivírus e reiniciei")
  viram lista: uma ação por linha, começando com "- ", no particípio
  ("- Atualizado o antivírus;").

## Requisição de Serviço
- Matrícula do usuário afetado, edifício, fila e técnico atribuído são o
  que o técnico costuma informar. Se faltar algum, pergunte.
- Tombo: são os 6 últimos dígitos do código da máquina
  (FCBVCUSTO265287 → 265287). O sistema faz esse corte sozinho.
- Uma requisição por tombo. O tombo vai na descrição e no Item B (com `*`).
- Resumo: "Requisição de Serviço". Categoria: quase sempre "Configuração".
