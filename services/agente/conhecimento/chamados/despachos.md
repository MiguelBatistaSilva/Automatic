# Modelos de despacho ao Serviço de Operações

Testes e defeito que vão no script do despacho (condenar equipamento), por
DEFEITO. Vieram da colinha da equipe (26/10), padronizados.

LIDO SÓ PELO CÓDIGO — não vai para a IA (seria muito texto a cada pedido).
A IA recebe só os NOMES dos modelos e escolhe um; os testes e o defeito
saem daqui exatamente como estão escritos. O técnico confere no cartão.

FORMATO (o código lê este arquivo): cada modelo é um título `##` seguido de
- tipo: Computador, Notebook, Monitor, Impressora, Teclado, Mouse, Webcam ou Caixa de som;
- pedidos: palavras que o técnico usa para esse defeito (vírgula);
- defeito: a conclusão (uma frase);
- testes: e, embaixo, um teste por linha começando com "  - ".
Sem pontuação no fim das linhas: o script põe o ";" sozinho.
Escrita: "Realizado teste...", "Realizada limpeza/inspeção/verificação...",
resultado depois da vírgula (ok, sem sucesso) ou dos dois-pontos (o que foi
constatado). Para criar um modelo novo, copie um bloco e ajuste.

## Computador — tela azul
- tipo: Computador
- pedidos: tela azul, bsod, erro de tela azul
- defeito: Erro de tela azul persistente após todos os testes efetuados
- testes:
  - Realizado teste do SSD, ok
  - Realizado teste de memória, ok
  - Realizado teste com outra fonte, ok
  - Realizados testes com outro SSD, sem sucesso: apresentou o mesmo erro de tela azul
  - Realizada formatação via rede, sem sucesso
  - Realizada formatação via pen drive, sem sucesso
  - Realizada formatação via HD externo, sem sucesso
  - Realizada troca do cabo de rede para a formatação via rede, sem sucesso
  - Realizada troca da pasta térmica, sem sucesso
  - Realizada atualização da BIOS, sem sucesso

## Computador — não liga
- tipo: Computador
- pedidos: não liga, nao liga, sem energia, não dá sinal, placa-mãe, curto
- defeito: Falha no circuito de alimentação da placa-mãe, impedindo a inicialização do computador
- testes:
  - Realizado teste da fonte de alimentação, utilizando método de aferição, sem sucesso
  - Realizado teste com a fonte de alimentação de outro computador, sem sucesso
  - Realizado teste dos cabos de energia e da conexão elétrica, ok
  - Realizado teste da memória RAM original (remoção e limpeza dos slots), sem sucesso
  - Realizado teste de substituição da memória RAM por módulo funcional de outro computador, sem sucesso
  - Realizado Clear na CMOS, sem sucesso
  - Realizado teste da bateria CMOS original, sem sucesso
  - Realizado teste de substituição da bateria CMOS por componente funcional de outro computador, sem sucesso
  - Realizado teste de troca da bateria CMOS por uma nova, sem sucesso
  - Realizado teste do SSD do computador defeituoso em outro computador, ok
  - Realizado teste de substituição do SSD por unidade funcional de outro computador, sem sucesso
  - Realizado teste apenas com os componentes essenciais (placa-mãe, processador, memória e fonte), sem sucesso
  - Realizada troca da pasta térmica do processador, sem sucesso
  - Realizada inspeção da placa-mãe (capacitores e slots): identificado defeito no circuito de alimentação

## Computador — FAN (conector da placa-mãe)
- tipo: Computador
- pedidos: fan, cooler, ventoinha, conector da fan, conector da placa
- defeito: Defeito nos conectores da placa-mãe, impossibilitando o funcionamento da FAN
- testes:
  - Realizado teste da FAN original, verificando alimentação e rotação, sem sucesso
  - Realizado teste de substituição da FAN por componente funcional de outro computador, sem sucesso
  - Realizado teste da conexão da FAN na placa-mãe, sem sucesso
  - Realizado teste em diferentes conectores FAN da placa-mãe, sem sucesso
  - Realizada inspeção visual do cabo e do conector da FAN: sem anormalidades aparentes
  - Realizada limpeza da FAN e do conector de alimentação, sem sucesso
  - Realizado reset da BIOS/CMOS para descartar falha de configuração, sem sucesso
  - Realizado teste da bateria CMOS original, sem sucesso
  - Realizado teste de substituição da bateria CMOS por componente funcional de outro computador, sem sucesso
  - Realizado teste de troca da bateria CMOS por uma nova, sem sucesso
  - Realizada verificação das configurações de controle de ventoinha na BIOS, sem sucesso
  - Realizado teste apenas com os componentes essenciais (placa-mãe, processador, memória e fonte), sem sucesso
  - Realizada inspeção da placa-mãe: identificada falha no circuito de alimentação/controladora da FAN

## Computador — FAN (ventoinha)
- tipo: Computador
- pedidos: fan, cooler, ventoinha, fan não gira, fan barulho
- defeito: Defeito na própria FAN, impossibilitando seu acionamento e funcionamento adequado
- testes:
  - Realizado teste de alimentação da FAN no equipamento, sem sucesso
  - Realizado teste da FAN em outro computador funcional, sem sucesso
  - Realizado teste da conexão da FAN na placa-mãe, ok
  - Realizado teste em diferentes conectores FAN da placa-mãe, sem sucesso
  - Realizada inspeção visual do cabo e do conector da FAN: identificado desgaste no componente
  - Realizada limpeza da FAN e dos conectores, sem sucesso
  - Realizado reset da BIOS/CMOS para descartar falha de configuração, sem sucesso
  - Realizado teste da bateria CMOS original: sem impacto na falha apresentada
  - Realizada verificação das configurações de controle de ventoinha na BIOS, ok
  - Realizado teste de substituição da FAN por outra unidade funcional: equipamento voltou a operar normalmente

## Computador — porta de rede (RJ45)
- tipo: Computador
- pedidos: rede, rj45, ethernet, porta de rede, placa de rede, sem rede, cabo de rede
- defeito: Falha na porta Ethernet do computador, impossibilitando a conexão de rede cabeada. Identificado defeito físico no circuito/interface de rede da placa-mãe. Necessária substituição da placa-mãe ou utilização de adaptador de rede externo para restabelecimento da conectividade
- testes:
  - Realizado teste do cabo de rede em outro equipamento, ok
  - Realizado teste com cabo de rede funcional, sem sucesso
  - Realizado teste em diferentes portas do switch, sem sucesso
  - Realizado teste de conectividade utilizando outro ponto de rede, sem sucesso
  - Realizada troca do cabo do patch panel para o switch, sem sucesso
  - Realizada reinstalação e atualização do driver da placa de rede, sem sucesso
  - Realizado teste de inicialização em modo de segurança com rede, sem sucesso
  - Realizado reset das configurações de rede do sistema operacional, sem sucesso
  - Realizada desinstalação e reinstalação do adaptador de rede, sem sucesso
  - Realizado teste com sistema operacional alternativo para validação de hardware, sem sucesso
  - Realizada validação das configurações de rede e DHCP, ok
  - Realizada inspeção física da porta Ethernet: identificado desgaste/dano nos contatos internos
  - Realizado teste de conexão utilizando adaptador de rede USB, ok
  - Realizado teste de comunicação com a rede local e a internet pela porta Ethernet, sem sucesso

## Computador — saída HDMI
- tipo: Computador
- pedidos: hdmi do computador, saída hdmi, sem vídeo, sem imagem, porta hdmi
- defeito: Falha na porta HDMI do computador, sem saída de vídeo
- testes:
  - Realizado teste do monitor em outro computador, utilizando a mesma entrada HDMI, ok
  - Realizado teste de substituição do cabo HDMI por um novo, sem sucesso
  - Realizado teste da tomada/energia elétrica, ok
  - Realizado teste apenas com os componentes essenciais (placa-mãe, processador, memória e fonte): sem vídeo na HDMI
  - Realizado teste das saídas de vídeo do computador (HDMI/VGA/DisplayPort): identificada falha na saída HDMI
  - Realizada limpeza da porta HDMI do computador, sem sucesso

## Computador — portas USB
- tipo: Computador
- pedidos: usb, portas usb, usb não funciona, usb intermitente
- defeito: Indícios de falha no circuito controlador USB da placa-mãe
- testes:
  - Realizado teste das portas USB frontais e traseiras: funcionamento intermitente
  - Realizado teste com diferentes dispositivos USB (mouse, teclado, pen drive): funcionamento intermitente
  - Realizado teste dos dispositivos USB em outro computador, ok
  - Realizada verificação de energia nas portas USB via BIOS e sistema operacional, sem sucesso
  - Realizada atualização e reinstalação dos drivers USB do sistema, sem sucesso
  - Realizado teste de inicialização por pen drive bootável: funcionamento intermitente
  - Realizada inspeção visual dos conectores USB na placa-mãe: sem danos aparentes
  - Realizado teste com hub USB alimentado externamente, sem sucesso
  - Realizado teste de continuidade e inspeção dos conectores internos do painel frontal USB, ok
  - Realizado teste apenas com os componentes essenciais (placa-mãe, processador, memória e fonte), sem sucesso

## Mouse — botão esquerdo
- tipo: Mouse
- pedidos: botão esquerdo, clique esquerdo, clique fantasma, clicando sozinho, clique duplo sozinho
- defeito: Botão esquerdo com ocorrência de cliques fantasmas e falhas de acionamento
- testes:
  - Realizado teste no botão esquerdo: defeituoso
  - Realizado teste no botão direito, ok
  - Realizado teste de clique duplo, ok
  - Realizado teste de rolagem com o scroll, ok
  - Realizado teste de clique central, ok
  - Realizado teste de arrasto, sem sucesso
  - Realizado teste de cliques rápidos e repetidos, sem sucesso
  - Realizado teste de estabilidade do clique, sem sucesso
  - Realizado teste de latência de resposta, ok
  - Realizado teste em outro computador, sem sucesso
  - Realizado teste em diferentes portas USB, sem sucesso
  - Realizada configuração do mouse nas configurações nativas do computador, sem sucesso
  - Realizada reinstalação dos drivers do mouse, sem sucesso
  - Realizado teste somente com o mouse no computador, retirando todos os outros periféricos, sem sucesso

## Mouse — botão direito
- tipo: Mouse
- pedidos: botão direito, clique direito
- defeito: Botão direito com ocorrência de cliques fantasmas e falhas de acionamento
- testes:
  - Realizado teste no botão direito: defeituoso
  - Realizado teste no botão esquerdo, ok
  - Realizado teste de clique duplo, ok
  - Realizado teste de rolagem com o scroll, ok
  - Realizado teste de clique central, ok
  - Realizado teste de arrasto, ok
  - Realizado teste de cliques rápidos e repetidos, sem sucesso
  - Realizado teste de estabilidade do clique, sem sucesso
  - Realizado teste de latência de resposta, ok
  - Realizado teste em outro computador, sem sucesso
  - Realizado teste em diferentes portas USB, sem sucesso
  - Realizada configuração do mouse nas configurações nativas do computador, sem sucesso
  - Realizada reinstalação dos drivers do mouse, sem sucesso
  - Realizado teste somente com o mouse no computador, retirando todos os outros periféricos, sem sucesso

## Mouse — scroll
- tipo: Mouse
- pedidos: scroll, rolagem, rodinha
- defeito: Comportamento irregular na rolagem, apresentando travamentos intermitentes e rolagem descontrolada para cima e para baixo, mesmo sem movimentação contínua do botão
- testes:
  - Realizado teste no botão esquerdo, ok
  - Realizado teste no botão direito, ok
  - Realizado teste de clique duplo, ok
  - Realizado teste de rolagem com o scroll: defeituoso
  - Realizado teste de clique central, ok
  - Realizado teste de arrasto, ok
  - Realizado teste de cliques rápidos e repetidos, ok
  - Realizado teste de estabilidade do clique, ok
  - Realizado teste de latência de resposta, ok
  - Realizado teste em outro computador, sem sucesso
  - Realizado teste em diferentes portas USB, sem sucesso

## Teclado — teclas sem resposta
- tipo: Teclado
- pedidos: teclado, teclas, tecla emperrada, tecla não funciona, não digita
- defeito: Teclado sem resposta ao acionamento das teclas, inclusive em outro computador, evidenciando falha no próprio teclado
- testes:
  - Realizado teste individual de todas as teclas alfanuméricas, sem resposta
  - Realizado teste das teclas de função (F1 a F12), sem resposta
  - Realizado teste das teclas modificadoras (Shift, Ctrl, Alt, Windows), sem resposta
  - Realizado teste da barra de espaço, sem resposta
  - Realizado teste da tecla Enter, sem resposta
  - Realizado teste das teclas Backspace/Delete, sem resposta
  - Realizado teste do teclado numérico, sem resposta
  - Realizado teste das setas direcionais, sem resposta
  - Realizado teste de simultaneidade (pressionamento de várias teclas), sem resposta
  - Realizado teste de latência/resposta das teclas, sem resposta
  - Realizado teste de repetição automática, sem resposta
  - Realizado teste em outro computador, sem resposta
  - Realizado teste em diferentes portas USB, sem resposta
  - Realizado teste com outro teclado no mesmo computador, ok
  - Realizada reinstalação e alteração dos drivers do teclado, sem resposta
  - Realizada atualização do Windows para atualização automática de driver, sem resposta

## Webcam — mau contato no cabo
- tipo: Webcam
- pedidos: webcam, câmera, camera, intermitente, mau contato, não reconhece
- defeito: Mau contato no cabo da webcam, próximo ao conector USB, comprometendo sua conexão
- testes:
  - Realizado teste da webcam em diferentes portas USB (frontais e traseiras): funcionamento intermitente
  - Realizado teste da webcam em outro computador: funcionamento intermitente, com falhas de conexão
  - Realizado teste com movimentação do cabo da webcam: constatado mau contato próximo ao conector USB
  - Realizado teste de outros dispositivos USB (mouse, teclado, pen drive) nas mesmas portas, ok
  - Realizada atualização e reinstalação dos drivers da webcam, sem sucesso
  - Realizada inspeção visual do cabo e do conector USB da webcam: identificado desgaste próximo ao conector

## Monitor — não liga
- tipo: Monitor
- pedidos: monitor não liga, sem energia, não acende, fonte do monitor
- defeito: Falha na placa de fonte interna ou no circuito de alimentação do monitor
- testes:
  - Realizado teste do cabo de energia do monitor defeituoso em outro equipamento, ok
  - Realizado teste de substituição do cabo de energia do monitor defeituoso por outro funcional, sem sucesso
  - Realizado teste da tomada/energia elétrica, ok
  - Realizado teste do botão liga/desliga (power), sem sucesso
  - Realizado teste das conexões de vídeo (HDMI/VGA/DisplayPort) em outro computador, sem sucesso
  - Realizado teste de substituição do cabo de vídeo por outro funcional, sem sucesso
  - Realizado teste em outro computador com o mesmo monitor, sem sucesso
  - Realizado teste em outra fonte de energia (tomada diferente/estabilizador/nobreak), sem sucesso

## Monitor — entrada HDMI
- tipo: Monitor
- pedidos: hdmi, entrada hdmi, sem sinal hdmi
- defeito: Falha na porta HDMI ou no circuito interno responsável pelo processamento do sinal HDMI do monitor
- testes:
  - Realizado teste do cabo HDMI em outro equipamento, ok
  - Realizado teste de substituição do cabo HDMI por outro funcional, sem sucesso
  - Realizado teste da entrada HDMI do monitor com diferentes computadores, sem sucesso
  - Realizado teste em diferentes portas HDMI dos equipamentos utilizados, sem sucesso
  - Realizado teste com o monitor configurado para a fonte de entrada HDMI correta, sem sucesso
  - Realizado reset das configurações do monitor, sem sucesso
  - Realizado teste em outra fonte de energia (tomada diferente/estabilizador/nobreak), sem sucesso

## Monitor — entrada DisplayPort
- tipo: Monitor
- pedidos: displayport, display port, entrada displayport, dp
- defeito: Falha na porta DisplayPort ou no circuito interno responsável pelo processamento do sinal DisplayPort do monitor
- testes:
  - Realizado teste do cabo DisplayPort em outro equipamento, ok
  - Realizado teste de substituição do cabo DisplayPort por outro funcional, sem sucesso
  - Realizado teste da entrada DisplayPort do monitor com diferentes computadores, sem sucesso
  - Realizado teste em diferentes portas DisplayPort dos equipamentos utilizados, sem sucesso
  - Realizado teste com o monitor configurado para a fonte de entrada DisplayPort correta, sem sucesso
  - Realizado reset das configurações do monitor, sem sucesso
  - Realizado teste em outra fonte de energia (tomada diferente/estabilizador/nobreak), sem sucesso

## Monitor — entrada VGA
- tipo: Monitor
- pedidos: vga, entrada vga, sem sinal vga
- defeito: Falha na porta VGA ou no circuito interno responsável pelo processamento do sinal VGA do monitor
- testes:
  - Realizado teste do cabo VGA em outro equipamento, ok
  - Realizado teste de substituição do cabo VGA por outro funcional, sem sucesso
  - Realizado teste da entrada VGA do monitor com diferentes computadores, sem sucesso
  - Realizado teste em diferentes equipamentos utilizando a conexão VGA, sem sucesso
  - Realizado teste com o monitor configurado para a fonte de entrada VGA correta, sem sucesso
  - Realizado reset das configurações do monitor, sem sucesso
  - Realizado teste em outra fonte de energia (tomada diferente/estabilizador/nobreak), sem sucesso

## Caixa de som — ruído
- tipo: Caixa de som
- pedidos: caixa de som, caixinha de som, ruído, chiado, chiando, barulho, som ruim
- defeito: Após todos os procedimentos descritos, o ruído excessivo permaneceu, inclusive nos testes em outro computador, evidenciando que a falha está na própria caixa de som
- testes:
  - Realizada troca da porta USB de alimentação, em diferentes portas disponíveis no equipamento
  - Realizado teste da caixa de som em outro computador, para descartar falha do equipamento de origem
  - Realizada verificação e atualização dos drivers de áudio do sistema operacional
  - Realizada desinstalação e reinstalação dos drivers de áudio
  - Realizado ajuste e reconfiguração das propriedades de som do sistema
  - Realizada habilitação e desabilitação dos recursos de som espacial
  - Realizada alteração da taxa de amostragem e da qualidade de áudio nas configurações avançadas
  - Realizada desativação dos aprimoramentos de áudio do sistema
  - Realizados testes com diferentes níveis de volume e balanceamento dos canais
  - Realizada verificação de interferências eletromagnéticas de outros dispositivos próximos
  - Realizada reinicialização e reconfiguração dos dispositivos de reprodução padrão do Windows
