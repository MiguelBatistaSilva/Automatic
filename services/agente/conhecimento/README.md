# Base de conhecimento do Assistente

Tudo o que o Assistente precisa SABER sobre o CATI e o Assyst mora aqui, em
arquivos de texto — um assunto por arquivo. Criada em 2026-10-01 para
centralizar o que estava espalhado (prompt no código, descrição das
ferramentas, tabela "Tipos de Solicitação" em Configurações).

Como funciona:
- Todo arquivo `.md` desta pasta (menos este README) vai para as instruções
  do Assistente, na ordem alfabética do nome do arquivo.
- `tipos_solicitacao.md` também é LIDO PELO CÓDIGO (ferramenta de Requisição
  por tombo): respeite o formato descrito lá.
- Para ensinar algo novo ao Assistente: edite ou crie um arquivo aqui. A
  atualização do app leva para todos os técnicos.

Não escreva aqui:
- Senhas, chaves, matrículas ou dados de usuários.
- O passo a passo de clique dos fluxos (isso é código, em services/flow_*).

Quando a base crescer muito, o Assistente passa a buscar só os trechos
relevantes de cada pedido (RAG) em vez de receber tudo — por isso, um
assunto por arquivo e títulos claros.
