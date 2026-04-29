# Automatic v6.0

Ferramenta de automação para o Assyst/TJCE.

---

## Requisitos

- Windows 10/11 64-bit;
- Python 3.11 ou superior instalado;
- Google Chrome instalado;
- `chromedriver.exe` compatível com sua versão do Chrome;

---

## Instalação

1. Copie a pasta `Automatic v6.0` para seu computador (ex: `C:\Automatic v6.0`);
2. Instale o python (você encontrará o executável na pasta Instalar_Python);
   - Selecione a opção Add python.exe to PATH na hora da instalação.
3. Coloque o `chromedriver.exe` dentro de `services\driver\`;
4. Clique duas vezes em `iniciar_automatic.bat`;
   - Na primeira execução, instala as dependências automaticamente,
   - Aguarde alguns minutos.

---

## Como verificar a versão do Chrome

1. Abra o Chrome;
2. Acesse: `chrome://version`;
3. Anote os primeiros numeros — ex: `136.0.7103.x`.

## Como baixar o chromedriver correto

Acesse: `https://googlechromelabs.github.io/chrome-for-testing/`

Baixe a versão correspondente ao seu Chrome para **Windows 64-bit**.

Extraia e coloque o `chromedriver.exe` em `services\driver\`.

---

## Como usar

### Aba Automatic

1. **Referência PAI** — informe o número do chamado que será desmembrado;
2. **Matrícula e Senha** — suas credenciais do sistema Assyst;
3. **Descrição** — texto que sera inserido em cada chamado filho;
4. **Base de Conhecimento** — selecione a BC que será vinculada;
5. **Dados de Iteração** — cole os dados que cada chamado filho deve ter;
   - Primeira linha = cabecalho (ex: `Marca/Modelo,Tombo`)
   - Demais linhas = dados
6. Clique em **Importar CSV** para validar;
7. Clique em **INICIAR** para executar.

### Aba Licence

Esta aba é uma automação dedicada para realizar login no Assyst caso todas as licenças estejam
em uso.

### Aba Bases de Conhecimento

Gerencie as BC's disponíveis para seleção na aba de execução.

- **Palavra-chave** — termo usado para pesquisar a BC no Assyst;
- **Título do Artigo** — nome exato da BC como aparece no sistema.

---

## Atualizações

Quando houver uma nova versão disponível:

1. Abra o terminal na pasta do projeto;
2. Execute: `git pull`;
3. Reinicie a aplicação.

---

## Problemas comuns

**Chrome não abre:**
- Verifique se o `chromedriver.exe` esta em `services\driver\`;
- Verifique se a versao do chromedriver e compatível com o Chrome instalado.

**Login não funciona:**
- Verifique suas credenciais;
- O sistema Assyst pode estar fora do ar.

**Importar CSV:**
- Na hora de importar os dados, certifique-se de que a primeira linha é o cabaçalho;
- Certifique-se que os valores estão separados por vírgulas.

---

## Suporte

Em caso de problemas, entre em contato com a equipe CATI.