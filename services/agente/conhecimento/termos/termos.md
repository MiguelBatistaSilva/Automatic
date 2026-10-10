# Termos (troca de máquina e tarefa de demanda)

São DOIS termos diferentes — escolha pelo assunto do pedido:
- TROCA DE MÁQUINA (micro, computador, backup, tombo, "termo de
  responsabilidade") -> gerar_termo.
- EVENTO / TAREFA DE DEMANDA (demanda, evento, apoio, transmissão,
  validador, "comprovação de prestação de serviço") -> gerar_termo_demanda.
- Se o técnico só disser "termo" e não der para saber qual, pergunte:
  "É o termo de troca de máquina ou o de tarefa de demanda (evento)?"

Achar o chamado (os dois): se ele citar o nome do usuário ("o chamado do
Gabriel"), use buscar_chamado_por_usuario.

## Termo de troca de máquina (gerar_termo)

- Uma máquina ou várias vão no MESMO termo (uma entrada em `maquinas` para
  cada troca).
- "Sem backup", "não backup", "não precisou de backup" = backup false.
  "Com backup", "fiz o backup" = backup true. Se o técnico não disser,
  pergunte.
- Nome, matrícula e unidade do usuário o SISTEMA lê do chamado: não
  pergunte.
- As máquinas: pergunte UMA vez, tudo junto, para cada troca: a que SAIU e
  a que ENTROU (marca/modelo, tombo, nº de série, hostname). O que o técnico
  não souber fica em branco — gere assim mesmo, não insista.
- Com backup: se o técnico disser se o backup pelo OneDrive foi oferecido,
  preencha `onedrive`; se não disser, deixe sem marcar (não pergunte).

## Termo de tarefa de demanda (gerar_termo_demanda)

- O SISTEMA lê do chamado: solicitante, local, data, horário previsto,
  descrição do evento e o técnico. NÃO pergunte esses dados, e não peça
  nem repita a descrição do chamado.
- Pergunte UMA vez, tudo junto, o que só o técnico sabe: quem é o
  VALIDADOR (nome e matrícula — nem sempre é quem abriu o chamado), o
  horário em que ele COMEÇOU e TERMINOU de fato, e a OBS (o que ele fez).
- O que o técnico não souber fica em branco; sem horário de execução, vale
  o agendado do chamado.
- `local` e `descricao` só se o técnico corrigir o que veio do chamado.

Os dois são gerados no computador do técnico, não mexem no Assyst. Anexar
o termo ao chamado ainda não é possível.
