import pyautogui
import time
from notion import write

def flow_printer(df, secretaria, log):
    log("Criando Requisição de Serviço...", tipo="status")

    time.sleep(2)
    pyautogui.PAUSE = 0.5

    # === GERAR DESCRIÇÃO DO CHAMADO PAI EM LISTA DE TÓPICOS ===
    description_father = f"Solicito instalação da impressora nos micros da {secretaria}:\n\n"
    for _, row in df.iterrows():
        description_father += f" - {row['MARCA/MODELO']} | Tombo: {row['TOMBO ANTIGO']}/{row['TOMBO NOVO']} | Nome: {row['NOME']}\n"

    # Usuário afetado
    pyautogui.click(x=-1962, y=462)
    write('400566')
    pyautogui.press('down')
    pyautogui.press('enter')

    # Título
    pyautogui.click(x=-1911, y=616)
    write('Instalação da Impressora')

    # Descrição
    pyautogui.click(x=-1730, y=730)
    write(description_father)

    # Produto
    pyautogui.click(x=-1807, y=1020)
    write('Serviço de Impressão e Digitalização')
    pyautogui.press('down')
    pyautogui.press('enter')

    # Item
    pyautogui.click(x=-1157, y=1016)
    write('Serviço de Impressão')
    pyautogui.press('down')
    pyautogui.press('enter')

    # Produto B
    pyautogui.click(x=-1716, y=1084)
    write('Digitalização e Impressão')
    pyautogui.press('down')
    pyautogui.press('enter')

    # Item B
    pyautogui.click(x=-1164, y=1090)
    write('Impressoras')
    pyautogui.press('down')
    pyautogui.press('enter')

    # Categoria
    pyautogui.click(x=-1939, y=1156)
    write('Configuração')
    time.sleep(0.8)
    pyautogui.press('down')
    pyautogui.press('enter')

    pyautogui.scroll(-200)

    # ---
    pyautogui.click(x=-1826, y=1099, clicks=3)
    pyautogui.press('delete')

    # Usuário atribuído
    pyautogui.click(x=-1507, y=1092)
    write('Miguel Batista')
    pyautogui.press('down')
    pyautogui.press('enter')

    # Salvar
    pyautogui.click(x=-887, y=302)
    time.sleep(5)

    log(f"Adicionando Base de Conhecimento", tipo="status")

    pyautogui.click(x=-946, y=294)
    time.sleep(5)
    pyautogui.click(x=-1902, y=535)
    pyautogui.hotkey('ctrl', 'a')
    pyautogui.press('delete')
    write('IMPRESSORA')
    pyautogui.click(x=-237, y=286)
    time.sleep(3)
    pyautogui.click(x=-1395, y=346)
    time.sleep(1)
    pyautogui.click(x=-1395, y=346)
    time.sleep(1)
    pyautogui.click(x=-1241, y=391, button='right')
    time.sleep(1.5)
    pyautogui.click(x=-1071, y=399)
    time.sleep(2)
    pyautogui.click(x=-267, y=1211)
    time.sleep(3)
    pyautogui.click(x=-102, y=301)
    time.sleep(3)

    log("Criando chamados remanescentes...", tipo="status")

    for _, row in df.iterrows():
        description_son = (f"Solicito instalação da impressora no micro da {secretaria}:\n\n"
                          f"{row['MARCA/MODELO']} | Tombo: {row['TOMBO ANTIGO']}/{row['TOMBO NOVO']} | Nome: {row['NOME']}")

        log(f"Inserindo micro {row['MARCA/MODELO']} - Tombo: {row['TOMBO NOVO']}")

        pyautogui.click(x=-985, y=294)
        time.sleep(1)
        pyautogui.click(x=-805, y=902)
        time.sleep(1)
        pyautogui.click(x=-1669, y=789)
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.press('delete')
        write(description_son)
        time.sleep(1)
        pyautogui.click(x=-897, y=299)
        time.sleep(5)

        log(f"Adicionando Base de Conhecimento...", tipo="status")

        pyautogui.click(x=-946, y=294)
        time.sleep(5)
        pyautogui.click(x=-1902, y=535)
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.press('delete')
        write('IMPRESSORA')
        pyautogui.click(x=-237, y=286)
        time.sleep(3)
        pyautogui.click(x=-1395, y=346)
        time.sleep(1)
        pyautogui.click(x=-1395, y=346)
        time.sleep(1)
        pyautogui.click(x=-1241, y=391, button='right')
        time.sleep(0.9)
        pyautogui.click(x=-1071, y=399)
        time.sleep(2)
        pyautogui.click(x=-267, y=1211)
        time.sleep(3)
        pyautogui.click(x=-102, y=301)
        time.sleep(5)

    log("Requisições criadas com sucesso!", tipo="status")

