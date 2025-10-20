import pyautogui
import time
from notion import write

# === CONFIGURAÇÕES ===
time.sleep(2)
pyautogui.PAUSE = 0.5

# Adicionando base
pyautogui.click(x=-946, y=294)
time.sleep(5)
pyautogui.click(x=-1902, y=535)
pyautogui.hotkey('ctrl', 'a')
pyautogui.press('delete')
write('NOMENCLATURA')
pyautogui.click(x=-237, y=286)
time.sleep(3)
pyautogui.click(x=-1395, y=346)
time.sleep(1)
pyautogui.click(x=-1395, y=346)
time.sleep(1)
pyautogui.click(x=-1092, y=427, button='right')
time.sleep(1.5)
pyautogui.click(x=-980, y=429)
time.sleep(3)
#pyautogui.click(x=-267, y=1211)
time.sleep(3)
#pyautogui.click(x=-102, y=301)
time.sleep(3)