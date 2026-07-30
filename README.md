# Automatic

Ferramenta de automação para o Assyst/TJCE.

Reúne módulos, como: desmembramento de chamados, início de atendimentos
agendados, análise de SLA e gerenciamento das Bases de Conhecimento.

A interface roda no navegador (Reflex) e a automação usa o Playwright, que dirige
o Chrome já instalado na máquina.

---

## Requisitos

- Windows 10/11 64-bit;
- Python 3.11 (o instalador acompanha o executável em `Instalar_Python`);
- Google Chrome instalado.

---

## Instalação

1. Copie a pasta do Automatic para seu computador (ex: `C:\Automatic`);
2. Instale o Python 3.11 (executável em `Instalar_Python\python-3.11.9-amd64.exe`);
   - **Marque a opção "Add Python to PATH"** durante a instalação.
3. Clique duas vezes em `iniciar_automatic.bat`.

Na **primeira execução**, o `iniciar_automatic.bat`:

- verifica se o Python 3.11 está disponível;
- cria o ambiente virtual (`.venv`);
- instala as dependências (usa os pacotes de `pacotes_automacao` quando existem e
  baixa o que faltar);
- sobe o servidor e abre a interface no navegador.

Nas execuções seguintes ele pula a instalação e vai direto para o app.

> **A janela preta é o aplicativo.** Enquanto você estiver usando o Automatic ela
> precisa ficar aberta — fechá-la encerra o programa. A interface fica em
> `http://localhost:3000`; se a página não abrir sozinha, digite esse endereço no
> navegador.

---

## Credenciais

As credenciais do Assyst são cadastradas **uma vez**, no menu **Opções →
Credenciais** (canto inferior da barra lateral). A matrícula fica num arquivo
local e a senha vai para o Cofre de Credenciais do Windows — nunca em texto
plano. Todos os módulos usam essas credenciais; nenhuma tela pede login de novo.

---

## Como usar

### Desmembramento

Duplica um chamado de referência em vários chamados filhos, um por linha da
planilha, e adiciona a Base de Conhecimento a eles. O seletor no topo escolhe as
etapas: **Criar + Base**, **Só Criar** ou **Só Base**.

1. **Referência** — número do chamado que será desmembrado;
2. **Base de Conhecimento** — selecione a BC que será vinculada;
3. **Descrição** — texto inserido em cada filho; use marcadores `{{COLUNA}}` para
   trocar pelos valores de cada linha;
4. **Dados de Iteração (CSV)** — cole os dados;
   - primeira linha = cabeçalho (ex: `Marca,Tombo`),
   - demais linhas = dados.
5. Clique em **Iniciar**.

Se uma execução for interrompida, o checkpoint é detectado no início seguinte e o
app pergunta se você quer **retomar** de onde parou ou **começar do zero**.

### Iniciar Atendimento

Inicia chamados que estão em Atendimento Programado na hora agendada. Adicione os
chamados com data/hora na tabela e clique em **Ativar**: a cada 20 segundos o app
verifica quem venceu e executa. O agendamento vive enquanto o app estiver aberto.

### Análise de SLA

Calcula o tempo líquido de SLA de um ou vários chamados, lendo o histórico de
ações de cada um no Assyst.

1. **Fila** — define o limite de SLA;
2. **Chamados** — cole um número por linha (ex: `S2123456`);
3. Clique em **Analisar SLA**.

Os resultados aparecem na tabela com início, tempo gasto, status (verde dentro do
prazo, vermelho estourado) e total de ações.

**Regras de cálculo do SLA:**

- O relógio só corre dentro do **expediente (08:00–21:00)**; fora dele congela;
- É **pausado** nas ações de espera (Aguardando Info do Usuário/Fornecedor/Gestor,
  Atendimento Programado) e **retomado** nas ações correspondentes;
- **Para de vez** nas ações de encerramento (Resolvido, Fechamento);
- O comportamento aos **fins de semana** depende da fila.

**Filas disponíveis:**

| Fila                                | Limite | Fim de semana |
|-------------------------------------|--------|---------------|
| 2N CATI FCB                         | 3h     | Congela       |
| 2N CATI Remoto                      | 2h     | Continua correndo |
| 2N CATI TJ                          | 3h     | Congela       |
| 2N CATI Demais Capital              | 6h     | Congela       |
| 2N CATI JUIZADO DA MULHER           | 3h     | Congela       |
| 2N CATI Vara de Custódia            | 2h     | Continua correndo |
| 2N CATI Sala de Imagem - Galpão BR  | 6h     | Congela       |
| 2N CATI Sala de Imagem - FCB        | 6h     | Congela       |

### Bases de Conhecimento

Gerencie as BCs disponíveis para seleção no Desmembramento.

- **Palavra-chave** — termo usado para pesquisar a BC no Assyst;
- **Título do Artigo** — nome exato da BC como aparece no sistema.

---

## Atualizações

Em **Opções → Sobre** você vê a versão instalada e pode verificar se há versão
nova. Havendo, o app mostra o link para baixar.

---

## Problemas comuns

**Python 3.11 não encontrado:**
- Execute `Instalar_Python\python-3.11.9-amd64.exe` e marque "Add Python to PATH";
- Feche e abra o `iniciar_automatic.bat` novamente.

**Falha na instalação das dependências:**
- O log do erro aparece na própria janela preta;
- Verifique a conexão e se a pasta `pacotes_automacao` está presente.

**A página não abriu no navegador:**
- Acesse `http://localhost:3000` manualmente;
- Na primeira execução o servidor demora mais para subir — atualize a página (F5).

**Chrome não abre durante a automação:**
- Confirme que o Google Chrome está instalado (o Playwright usa o Chrome do
  sistema).

**Login não funciona:**
- Confira as credenciais em Opções → Credenciais;
- O Assyst pode estar fora do ar.

**Análise de SLA sem resultados:**
- Confira se os números dos chamados estão corretos (um por linha);
- Veja no Registro de Execução se o histórico foi extraído.

---

## Suporte

Em caso de problemas, entre em contato com a equipe CATI.
