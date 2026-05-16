---
name: automatic-desktop
description: Arquitetura e fluxo de automação da versão desktop PyQt6 do projeto Automatic do TJCE. Use esta skill sempre que precisar entender, modificar ou criar arquivos da versão desktop — incluindo fluxos Selenium, abas PyQt6, checkpoint em JSON, kb_manager, driver_manager, locators ou qualquer componente do projeto desktop. Use também ao debugar erros de Chrome com interface gráfica, CKEditor, menu Dojo, checkpoint por chamado ou comportamentos específicos do ambiente Windows corporativo com firewall SSL.
---

# Automatic — Versão Desktop (PyQt6)

Aplicação desktop PyQt6 que roda no Windows com Chrome visível.
Automatiza abertura e gestão de chamados no sistema Assyst do TJCE.

---

## Arquitetura de pastas

```
Automatic/
  main.py                       ← entry point: QApplication, ícone, kb_store
  app_icon.ico                  ← ícone da aplicação
  iniciar_automatic.bat         ← cria .venv, instala pacotes offline, inicia app
  iniciar_automatic.vbs         ← launcher invisível (sem janela CMD)
  gerar_atalho.py               ← gera Automatic.lnk na área de trabalho
  data/
    checkpoints/                ← um JSON por chamado: {numero}.json
    filhos_{chamado}.txt        ← filhos acumulados por chamado (abre no Bloco de Notas)
    kb_configs.json             ← bases de conhecimento
  pacotes_automacao/            ← wheels para instalação offline (firewall corporativo)
  services/
    automatic.py                ← orquestrador: singleton DriverManager + executar_fluxo
    driver_manager.py           ← gerencia instância Chrome (singleton por sessão)
    flow_base.py                ← Criar + Base (Fase 1 + Fase 2)
    flow_3n.py                  ← Só Criar (apenas Fase 1)
    flow_bc.py                  ← Só Base (apenas Fase 2)
    flow_utils.py               ← helpers compartilhados: login, navegação, relogin, capturar filho, registrar filho, abrir TXT, montar_descricao, adicionar_bc
    kb_manager.py               ← adiciona Base de Conhecimento via menu de contexto (XPath DOM)
    kb_store.py                 ← leitura/gravação de kb_configs.json
    checkpoint.py               ← checkpoint por chamado em data/checkpoints/
    locators.py                 ← seletores Selenium centralizados
  ui/
    main_window.py              ← QMainWindow: abas + menu de links
    aba_execucao.py             ← aba principal: selectbox de modo + 3 painéis
    aba_kb.py                   ← gerenciamento de bases de conhecimento
    aba_license.py              ← login contínuo para capturar licença disponível
    tema_qt.py                  ← CSS global, cores, fontes
```

---

## Modos de operação

O `aba_execucao.py` tem um `QComboBox` com três modos:

| Modo | Fluxo | O que faz |
|---|---|---|
| 🔗 Criar + Base | `flow_base.py` | Duplica PAI + adiciona BC em cada filho |
| 📋 Só Criar | `flow_3n.py` | Duplica PAI sem BC |
| 📎 Só Base | `flow_bc.py` | Adiciona BC em chamados já criados |

---

## Ciclo de uma execução

```
Usuário clica INICIAR
        ↓
aba_execucao.py valida campos
        ↓
CheckpointDialog (se pendente): Retomar ou Começar do zero
        ↓
AutomacaoWorker (QThread): chama Automatic.executar_fluxo()
        ↓
automatic.py: obtém driver singleton → chama execute_*_flow()
        ↓
flow_base/3n/bc: login → navega → processa linhas → atualiza checkpoint JSON
        ↓
kb_manager.py: context_click → XPath DOM → clica item → salva → volta ao chamado
        ↓
Ao final: gera/acumula filhos_{chamado}.txt → abre no Bloco de Notas
        ↓
fim_signal → aba_execucao atualiza UI
```

---

## Driver — singleton por sessão

O `DriverManager` em `automatic.py` é um singleton global.
O Chrome abre uma vez e fica vivo entre execuções da mesma sessão.
Isso permite reutilizar a sessão do Assyst sem fazer login a cada fluxo.
A aba License usa o mesmo driver para capturar licença.

---

## Checkpoint — arquivo JSON por chamado

Cada chamado tem seu próprio arquivo em `data/checkpoints/{numero}.json`:

```json
{
  "numero_chamado": "S2111111",
  "total": 5,
  "concluido": false,
  "linhas": [
    {"index": 0, "status": "concluido"},
    {"index": 1, "status": "salvo", "numero_filho": "R2336676"},
    {"index": 2, "status": "pendente"}
  ]
}
```

Três estados por linha: `pendente` → `salvo` → `concluido`.
`salvo` significa chamado criado mas BC ainda não adicionada.
O fluxo retoma de onde parou consultando o JSON.

---

## Arquivo de filhos

`data/filhos_{chamado}.txt` acumula filhos sem duplicatas a cada execução.
Múltiplas execuções do mesmo chamado (bases diferentes) acumulam no mesmo arquivo.
Ao final de cada execução bem-sucedida, abre automaticamente no Bloco de Notas.

---

## Peculiaridades do ambiente Windows corporativo

| Problema | Solução |
|---|---|
| Firewall SSL bloqueia pip | `--trusted-host pypi.org --trusted-host files.pythonhosted.org` no download |
| Instalação offline | Pasta `pacotes_automacao/` com wheels + `--no-index --find-links` |
| Ícone não aparece na barra | `pythonw.exe` + atalho `.lnk` com `.ico` via `pywin32` |
| Janela CMD ao iniciar | `.vbs` launcher que chama o `.bat` com `WScript.Shell Run ... 0` |

---

## Instalação para o usuário

```
1ª vez:
  Clica em iniciar_automatic.bat
    → cria .venv
    → instala pacotes offline
    → gera Automatic.lnk na área de trabalho

Da 2ª vez em diante:
  Clica em Automatic.lnk
    → sem janela CMD
    → ícone correto na barra de tarefas
```

---

## Montagem da descrição — sistema de marcadores

A função `_montar_descricao(template, row)` em `flow_utils.py` substitui
marcadores `{{NOME_COLUNA}}` pelo valor correspondente da linha do CSV.
É importada por `flow_base.py` e `flow_3n.py`.

```python
# Template no campo Descrição:
# • MARCA: {{MARCA}}
# • TOMBO: {{TOMBO}}

# CSV:
# MARCA,TOMBO
# LENOVO,262471

# Resultado no chamado:
# • MARCA: LENOVO
# • TOMBO: 262471
```

Colunas sem marcador correspondente são ignoradas silenciosamente.
Marcadores sem valor no CSV ficam em branco.

---

## Aba License

Worker separado (QThread) que faz login em loop contínuo até conseguir uma licença.
Usa o mesmo `DriverManager` singleton dos fluxos.
Útil quando todas as licenças do Assyst estão ocupadas.

---

## Preenchimento do CKEditor

O `send_keys` não funciona de forma confiável no CKEditor.
A solução correta é usar a API `setData()` do CKEditor a partir do frame principal,
sem entrar no iframe. O nome da instância é fixo: `rtES1_formattedRemarks`.

O campo que o servidor recebe é o hidden `ES1_formattedRemarks`. O CKEditor sincroniza
seu modelo interno com esse hidden no momento do save. Por isso `body.innerHTML` no
iframe (camada visual apenas) não funciona — o modelo interno fica desatualizado.

```python
# Aguardar o CKEditor estar pronto (iframe visível = editor inicializado)
WebDriverWait(driver, 20).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, "iframe.cke_wysiwyg_frame"))
)
time.sleep(0.5)

# Injetar via API oficial — atualiza modelo interno e campo hidden
html = description_son.replace("\n\n", "</p><p>").replace("\n", "<br>")
html = "<p>" + html + "</p>"
driver.execute_script(
    "CKEDITOR.instances['rtES1_formattedRemarks'].setData(arguments[0]);",
    html
)
```

---

## Adição de BC via menu de contexto (XPath DOM)

O menu de contexto é acionado com `context_click` no artigo localizado na grade Dojo.
O item do menu é encontrado por XPath via texto visível em português: `"Ação de Solução de Conhecimento"`.
Após salvar, o fluxo clica em "Voltar ao evento" para retornar ao chamado.

```python
ActionChains(driver).context_click(artigo_elemento).perform()
time.sleep(0.9)

xpath_menu_item = "//td[contains(text(), 'Ação de Solução de Conhecimento')]/ancestor::tr[1]"
WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, xpath_menu_item))).click()
WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "ManageActionForm.btSave"))).click()

WebDriverWait(driver, 20).until(EC.invisibility_of_element_located((By.ID, "contentOverlay")))
xpath_voltar = "//span[text()='Voltar ao evento']/ancestor::span[contains(@role, 'button')]"
btn_voltar = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.XPATH, xpath_voltar)))
driver.execute_script("arguments[0].click();", btn_voltar)
```

A busca do artigo na grade usa scroll incremental no `.dojoxGridScrollbox` até localizar o texto
do `nome_artigo` via `innerText` das linhas `.dojoxGridRow` (ignora tags `<b>` internas).
