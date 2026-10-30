# Itens da Requisição

Lido SÓ pelo código (services/dados/referencia.py) — não vai para a IA.
Valores aceitos nos campos da Requisição de Serviço que não têm tabela
própria: item, item_b, categoria e resumo. O /requisicao do bot oferece
estes valores como botão, e o Assistente confere o Item por aqui. Os
técnicos, as filas e os edifícios vêm das outras tabelas desta pasta.
Escreva exatamente como no Assyst.

Colunas: campo (item, item_b, categoria ou resumo), valor, produto (só
no item: desde 29/10 o Assyst pede o Produto antes do Item), quando_usar.

`quando_usar` VAI PARA A IA (na ferramenta de Requisição): exemplos de
pedidos reais da equipe. O nome do item não diz qual usar — é convenção
(troca de ventoinha é Computador / Instalar / Configurar, não Hardware /
Substituir). Sem exemplo, a IA pergunta ao técnico. Caso novo = um exemplo
a mais aqui.

| campo | valor | produto | quando_usar |
|---|---|---|---|
| item | Computador | Estação de Trabalho | qualquer coisa no micro, inclusive troca de peça (ex.: ventoinha) |
| item | Notebook | Estação de Trabalho |  |
| item | Hardware | Equipamentos |  |
| item | Periféricos e Acessórios | Equipamentos |  |
| item | Impressoras e Scanners | Serviço de Impressão e Digitalização |  |
| item | Internet | Gestão de Acesso |  |
| item | Apoio a Eventos e Audiências | Apoio a Eventos e Audiências |  |
| item | Java | Software |  |
| item_b | IC NÃO LOCALIZADO |  |  |
| item_b | Impressoras |  |  |
| categoria | Alterar Acesso |  |  |
| categoria | Apoio Técnico em Evento ou Reunião |  |  |
| categoria | Conceder Acesso |  |  |
| categoria | Desativar acesso |  |  |
| categoria | Desinstalar |  |  |
| categoria | Devolver |  |  |
| categoria | Empréstimo |  |  |
| categoria | Empréstimo de Equipamentos para Eventos ou Reuniões |  |  |
| categoria | Empréstimo de Periféricos |  |  |
| categoria | Empréstimos de Computador |  |  |
| categoria | Implantação |  |  |
| categoria | Informação / Orientação Técnica |  |  |
| categoria | Instalar / Configurar |  | instalação, configuração e troca de peça no micro (ex.: ventoinha) |
| categoria | Liberar Site Bloqueado |  |  |
| categoria | Manutenção Preventiva |  |  |
| categoria | Movimentar / Remanejar |  |  |
| categoria | Movimentação / Remanejamento |  |  |
| categoria | Recolher Toner |  |  |
| categoria | Solicitar Toner |  |  |
| categoria | Substituir |  |  |
| categoria | Substituição |  |  |
| categoria | Teste de Equipamentos para Eventos e Reuniões |  |  |
| resumo | Requisição de Serviço |  |  |
