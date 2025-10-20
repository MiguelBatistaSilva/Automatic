import pyautogui
import time
import pandas as pd
from notion import write

# === CONFIGURAÇÕES ===
time.sleep(2)
pyautogui.PAUSE = 0.5

df = pd.read_excel('21JECC.xlsx')

# === GERAR DESCRIÇÃO DO CHAMADO PAI EM LISTA DE TÓPICOS ===
description_father = "Solicito organização de cabos nos micros da Diretoria da Fazenda:\n\n"
for _, row in df.iterrows():
    description_father += f" - {row['MARCA/MODELO']} | Tombo Antigo: {row['TOMBO ANTIGO']} | Tombo Novo: {row['TOMBO NOVO']} | Nome: {row['NOME']}\n"

# ----------------------------
# 1. Criação do PRIMEIRO chamado completo
# ----------------------------
print("Criando Chamado Pai...")

# Usuário afetado
pyautogui.click(x=-1962, y=462)
write('400726')
pyautogui.press('down')
pyautogui.press('enter')

# Título
pyautogui.click(x=-1911, y=616)
write('Organização de Micro')

# Descrição
pyautogui.click(x=-1730, y=730)
write(description_father)

# Produto
pyautogui.click(x=-1807, y=1020)
write('Equipamentos')
pyautogui.press('down')
pyautogui.press('enter')

# Item
pyautogui.click(x=-1157, y=1016)
write('Periféricos e Acessórios')
pyautogui.press('down')
pyautogui.press('enter')

# Produto B
pyautogui.click(x=-1716, y=1084)
write('A ser definido')
pyautogui.press('down')
pyautogui.press('enter')

# Item B
pyautogui.click(x=-1164, y=1090)
write('IC N')
pyautogui.press('down')
pyautogui.press('enter')

# Categoria
pyautogui.click(x=-1939, y=1156)
write('Configuração')
time.sleep(0.7)
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