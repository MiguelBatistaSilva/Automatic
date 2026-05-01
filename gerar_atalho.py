"""
gerar_atalho.py — Gera o atalho Automatic.lnk na area de trabalho do usuario.
Execute uma vez apos instalar o projeto:
    python gerar_atalho.py
"""
import os
import sys

try:
    import win32com.client
except ImportError:
    print("[ERRO] Modulo win32com nao encontrado.")
    print("       Execute: pip install pywin32")
    sys.exit(1)

# Caminhos
projeto_dir  = os.path.dirname(os.path.abspath(__file__))
vbs_path     = os.path.join(projeto_dir, "iniciar_automatic.vbs")
icone_path   = os.path.join(projeto_dir, "app_icon.ico")
desktop      = os.path.join(os.path.expanduser("~"), "Desktop")
atalho_path  = os.path.join(desktop, "Automatic.lnk")

if not os.path.exists(vbs_path):
    print(f"[ERRO] Arquivo nao encontrado: {vbs_path}")
    sys.exit(1)

if not os.path.exists(icone_path):
    print(f"[AVISO] Icone nao encontrado: {icone_path}")
    icone_path = ""

shell   = win32com.client.Dispatch("WScript.Shell")
atalho  = shell.CreateShortcut(atalho_path)

atalho.TargetPath       = vbs_path
atalho.WorkingDirectory = projeto_dir
atalho.Description      = "Automatic v6.0"

if icone_path:
    atalho.IconLocation = icone_path

atalho.Save()

print(f"[OK] Atalho criado em: {atalho_path}")