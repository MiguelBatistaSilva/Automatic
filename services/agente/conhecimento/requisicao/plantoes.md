# Plantões do fim de semana

- "Gere os chamados dos plantões (do final de semana)" = `criar_plantoes`.
  O sistema monta as Requisições: 3 por dia (Sede Judiciária, Fórum Clóvis
  Beviláqua e Custódia/Externo), com descrição, horário, item e fila fixos.
  Não use `criar_requisicoes` para plantão.
- Por dia, três técnicos: o da Sede, o do Fórum e o da Custódia (um pode
  repetir em mais de um local). Se o pedido não disser os nomes, chame `criar_plantoes` sem
  `dias`: o sistema devolve as datas para você perguntar.
- Datas: sem data dita, é o próximo sábado e domingo (deixe `data` vazio).
  Feriado ou outro dia: passe as datas (dd/mm), um item por dia.
- A matrícula do supervisor fica salva; só passe `matricula_supervisor` se o
  técnico informar ou disser que mudou.
