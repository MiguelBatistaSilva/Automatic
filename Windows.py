import pyautogui
import time
from notion import write

def flow_windows(df, secretaria, log):

    log("Adicionando Base de Conhecimento...")

    time.sleep(2)
    pyautogui.PAUSE = 0.4

    pyautogui.click(x=-946, y=294)
    time.sleep(5)
    pyautogui.click(x=-1902, y=535)
    pyautogui.hotkey('ctrl', 'a')
    pyautogui.press('delete')
    write('WINDOWSPE')
    pyautogui.click(x=-237, y=286)
    time.sleep(3)
    pyautogui.click(x=-1092, y=427, button='right')
    time.sleep(1)
    pyautogui.click(x=-980, y=429)
    time.sleep(2)
    pyautogui.click(x=-267, y=1211)
    time.sleep(3)
    pyautogui.click(x=-102, y=301)
    time.sleep(3)

    log("Criando chamados remanescentes...")

    for _, row in df.iterrows():
        description_son = (f"Solicito atualização de sistema para Windows 11 no micro da {secretaria}:\n\n"
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
        time.sleep(4)

        log(f"Adicionando Base de Conhecimento", tipo="status")

        pyautogui.click(x=-946, y=294)
        time.sleep(5)
        pyautogui.click(x=-1902, y=535)
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.press('delete')
        write('WINDOWSPE')
        pyautogui.click(x=-237, y=286)
        time.sleep(3)
        pyautogui.click(x=-1092, y=427, button='right')
        time.sleep(1)
        pyautogui.click(x=-980, y=429)
        time.sleep(2)
        pyautogui.click(x=-267, y=1211)
        time.sleep(3)
        pyautogui.click(x=-102, y=301)
        time.sleep(3)

    log("Requisições criadas com sucesso!", tipo="status")

