import time
import pyperclip
import pyautogui

def write(texts):
    pyperclip.copy(str(texts) if texts else "")
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.3)

def write_text(text):
    pyperclip.copy(text)   # copia para a área de transferência
    pyautogui.hotkey("ctrl", "v")  # cola no campo
    time.sleep(0.2)

