# Automatic

Ferramenta de automação para o Assyst/TJCE.

Atualmente reúne quatro módulos: desmembramento de chamados, análise de SLA,
login automático (License) e gerenciamento das Bases de Conhecimento.

---

## Requisitos

- Windows 10/11 64-bit;
- Python 3.11 (o instalador acompanha o executável em `Instalar_Python`);
- Google Chrome instalado;
- `chromedriver.exe` compatível com sua versão do Chrome.

---

## Instalação

1. Copie a pasta `Automatic v6.2` para seu computador (ex: `C:\Automatic v6.0`);
2. Instale o Python 3.11 (executável em `Instalar_Python\python-3.11.9-amd64.exe`);
   - **Marque a opção "Add Python to PATH"** durante a instalação.
3. Coloque o `chromedriver.exe` dentro de `services\driver\`;
4. Clique duas vezes em `iniciar_automatic.bat`.

Na **primeira execução**, o `iniciar_automatic.bat`:

- verifica se o Python 3.11 está disponível;
- cria o ambiente virtual (`.venv`) automaticamente;
- abre uma janela de instalação que instala as dependências **offline**, a partir
  da pasta `pacotes_automacao` (não precisa de internet);
- cria um atalho na área de trabalho.

Aguarde a janela de instalação concluir. Nas execuções seguintes o app abre
direto, sem reinstalar nada.

---

## Configurando o chromedriver

O `chromedriver.exe` precisa ser da mesma versão do seu Chrome. Em vez de
procurar uma versão antiga específica, **mantenha o Chrome atualizado** e baixe
o driver correspondente — assim os dois ficam sempre compatíveis.

1. **Atualize o Chrome:**
   - Abra o Chrome;
   - Acesse `chrome://settings/help`;
   - O Chrome verifica e instala a última versão automaticamente;
   - Clique em **Reiniciar** quando solicitado.

2. **Veja a versão instalada:**
   - Acesse `chrome://version`;
   - Anote os primeiros números — ex: `136.0.7103.x`.

3. **Baixe o chromedriver correspondente:**
   - Acesse `https://googlechromelabs.github.io/chrome-for-testing/`;
   - Baixe a versão correspondente ao seu Chrome para **Windows 64-bit**.

4. **Instale o driver:**
   - Extraia e coloque o `chromedriver.exe` em `services\driver\`.

---

## Como usar

### Aba 🤖 Desmembramento

Cria os chamados filhos a partir de um chamado pai.

1. **Referência PAI** — informe o número do chamado que será desmembrado;
2. **Matrícula e Senha** — suas credenciais do sistema Assyst;
3. **Descrição** — texto que será inserido em cada chamado filho;
4. **Base de Conhecimento** — selecione a BC que será vinculada;
5. **Dados de Iteração** — cole os dados que cada chamado filho deve ter;
   - Primeira linha = cabeçalho (ex: `Marca/Modelo,Tombo`)
   - Demais linhas = dados
6. Clique em **Importar CSV** para validar;
7. Clique em **INICIAR** para executar.

### Aba ⏱️ Análise de SLA

Calcula o tempo líquido de SLA de um ou vários chamados, lendo o histórico de
ações de cada um diretamente no Assyst.

1. **Matrícula e Senha** — suas credenciais do Assyst;
2. **Fila** — selecione a fila do chamado (define o limite de SLA);
3. **Chamados** — cole um número por linha (ex: `S2123456`);
4. (Opcional) clique em **Importar lista** para validar a quantidade;
5. Clique em **▶ Analisar SLA**.

Os resultados aparecem na tabela com início, tempo gasto, status (verde quando
dentro do prazo, vermelho quando estourado) e total de ações.

**Regras de cálculo do SLA:**

- O relógio só corre dentro do **expediente (08:00–21:00)**; fora dele congela;
- É **pausado** nas ações de espera (Aguardando Info do Usuário/Fornecedor/Gestor,
  Atendimento Programado) e **retomado** nas ações correspondentes;
- **Para de vez** nas ações de encerramento (Resolvido, Fechamento);
- O comportamento aos **fins de semana** depende da fila.

**Filas disponíveis:**

| Fila            | Limite | Fim de semana |
|-----------------|--------|---------------|
| 2N CATI FCB     | 3h     | Congela       |
| 2N CATI Remoto  | 2h     | Continua correndo |

### Aba 🔑 License

Automação dedicada para realizar login no Assyst quando todas as licenças
estão em uso.

### Aba 📚 Bases de Conhecimento

Gerencie as BCs disponíveis para seleção na aba de Desmembramento.

- **Palavra-chave** — termo usado para pesquisar a BC no Assyst;
- **Título do Artigo** — nome exato da BC como aparece no sistema.

---

## Atualizações

A aplicação verifica atualizações automaticamente ao iniciar.

Quando houver uma nova versão, uma janela de atualização será exibida. Ao
confirmar, o app baixa e aplica a atualização sozinho e reinicia — suas
configurações locais (pasta `data`, `.venv` e `pacotes_automacao`) são
preservadas.

---

## Problemas comuns

**Python 3.11 não encontrado:**
- Execute `Instalar_Python\python-3.11.9-amd64.exe` e marque "Add Python to PATH";
- Feche e abra o `iniciar_automatic.bat` novamente.

**Falha na instalação das dependências:**
- Verifique se a pasta `pacotes_automacao` está presente e completa;
- A janela de instalação mostra o log do erro.

**Chrome não abre:**
- Verifique se o `chromedriver.exe` está em `services\driver\`;
- Verifique se a versão do chromedriver é compatível com o Chrome instalado.

**Login não funciona:**
- Verifique suas credenciais;
- O sistema Assyst pode estar fora do ar.

**Importar CSV (Desmembramento):**
- Certifique-se de que a primeira linha é o cabeçalho;
- Certifique-se de que os valores estão separados por vírgulas.

**Análise de SLA sem resultados:**
- Confira se os números dos chamados estão corretos (um por linha);
- Verifique no log se o histórico do chamado foi extraído.

---

## Suporte

Em caso de problemas, entre em contato com a equipe CATI.
