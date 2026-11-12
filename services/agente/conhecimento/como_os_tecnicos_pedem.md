# Como os técnicos pedem

- Os técnicos costumam citar o chamado pelo NOME do usuário ("o chamado da
  Carla") e não pelo número. Nesse caso, procure o chamado
  (buscar_chamado_por_usuario) antes de qualquer ação. Se ele disse a fila
  ("o chamado do Marcos na fila do 2N CATI Demais Capital"), passe a fila;
  senão, deixe sem fila (o sistema olha a Minha Fila e depois a 2N CATI
  FCB). Se vierem vários, pergunte qual (mostrando nome e setor). Se o
  chamado estiver com OUTRO técnico, só avise ("esse está com o Fulano") e
  siga.
- "TODOS os chamados do Fulano" (ex.: "aplica a base X em todos os chamados
  da Carla"): busque com todos=true e use TODOS os que vierem na ação, sem
  perguntar; o técnico confere a lista no cartão.
- Filas: "Minha Fila" (os chamados atribuídos ao técnico) e as filas do
  Assyst (2N CATI FCB, 2N CATI TJ, 2N CATI Demais Capital, 2N CATI Sala de
  Imagem - FCB, 2N CATI Sala de Imagem - Galpão BR). "Analisa a minha fila"
  / "analisa a fila do 2N CATI FCB" → analisar_chamado com fila. Se ele
  disser só "a fila" sem dizer qual, pergunte qual.
  "Configurar/criar a fila X no Assyst" é outra coisa: é configurar_filas.
