# Base de conhecimento do Assistente

Tudo o que o Assistente precisa SABER sobre o CATI e o Assyst mora aqui, em
arquivos de texto. Criada em 2026-10-01; organizada POR DOMÍNIO em 07/10.

Organização:
- Cada SUBPASTA é um domínio: `chamados/`, `requisicao/`, `filas/` ... — um
  assunto por arquivo dentro dela, com um título `# Título` na 1ª linha.
- Arquivo na RAIZ (ex.: `como_os_tecnicos_pedem.md`) vale para todos os
  pedidos.

Como o Assistente usa:
- Um roteador (services/agente/roteador.py) vê de que domínio é o pedido e
  manda à IA só as ferramentas e os arquivos DAQUELE domínio, mais os da
  raiz. Na dúvida, manda tudo.
- A IA sempre recebe o ÍNDICE de todos os assuntos; se precisar de um de
  outro domínio, lê com a ferramenta `consultar_conhecimento`.
- `requisicao/tipos_solicitacao.md` também é LIDO PELO CÓDIGO (Requisição
  por tombo): respeite o formato descrito lá.

Para ensinar algo novo: edite ou crie um arquivo na pasta do domínio certo.
Domínio NOVO (ex.: documentos): crie a subpasta E avise quem programa — o
nome precisa existir também no roteador e no `dominio=` das ferramentas.
A atualização do app leva para todos os técnicos.

Não escreva aqui:
- Senhas, chaves, matrículas ou dados de usuários.
- O passo a passo de clique dos fluxos (isso é código, em services/flow_*).
