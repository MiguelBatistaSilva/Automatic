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
  não souber fica em branco — gere assim mesmo, não insista. Se ele já
  mandou as máquinas (mesmo só os tombos), NÃO pergunte de novo: gere.
- Como os técnicos escrevem: "saiu -> entrou", uma linha por troca, ou uma
  linha por campo. Ex.: "C6200 315016 1AM03Y878 -> Lenovo 333232 PE0FES1J"
  = saiu {marca_modelo "POSITIVO C6200", tombo "315016", serie "1AM03Y878"},
  entrou {marca_modelo "LENOVO", tombo "333232", serie "PE0FES1J"}.
  Número de 5 a 7 dígitos = tombo; código de letras e números = série;
  C6200, M70q… = modelo (nunca hostname).
- "Coloque o nome FCB13CRIM" / "hostname X" = hostname da máquina, NUNCA o
  nome do usuário. Na troca a nova quase sempre herda o nome da antiga: com
  UM hostname, o sistema repete nos dois lados. Se o técnico disser dois
  nomes (raro: a nova ganhou outro), ponha cada um no seu lado.
- Série e hostname que o técnico não disser, o SISTEMA busca no Itom pelo
  tombo: com o tombo, NÃO pergunte série nem hostname — gere.
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
- `descricao` só se o técnico corrigir o que veio do chamado.
- `local`: o que o técnico disse; senão, o que o Pedido do chamado diz (o
  sistema manda o Pedido quando a descrição não tem "Local:"). Não pergunte
  o local ao técnico: sem nada, o sistema usa o Edifício/Sala do chamado.

Os dois são gerados no computador do técnico, não mexem no Assyst. O PDF
gerado ainda precisa ser ASSINADO DIGITALMENTE (técnico e validador) antes
de valer: o técnico assina e anexa ao chamado por conta própria — o
Assistente não anexa termo.
