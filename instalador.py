"""
instalador.py — Janela de instalação com progresso.
Chamado pelo iniciar_automatic.bat na primeira execução.
Usa apenas tkinter (embutido no Python), sem dependências externas.
"""
import os
import sys
import subprocess
import threading
import tkinter as tk
from tkinter import ttk

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
VENV_PY   = os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe")
PACOTES   = os.path.join(BASE_DIR, "pacotes_automacao")
ATALHO_PY = os.path.join(BASE_DIR, "gerar_atalho.py")

PACOTES_LISTA = ["pandas", "selenium", "PyQt6", "pywin32", "requests"]

COR_FUNDO  = "#F5F7FA"
COR_TEXTO  = "#111827"
COR_MUTED  = "#6B7280"
COR_VERDE  = "#16A34A"
COR_ERRO   = "#DC2626"
COR_AZUL   = "#2563EB"


class JanelaInstalacao:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Configurando Automatic")
        self.root.resizable(False, False)
        self.root.configure(bg=COR_FUNDO)
        self._sucesso = False

        self._build_ui()
        self._centralizar(480, 340)

        # Impede fechar durante a instalação
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)

        threading.Thread(target=self._instalar, daemon=True).start()
        self.root.mainloop()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        tk.Label(
            self.root, text="Configurando Automatic",
            font=("Segoe UI", 14, "bold"),
            bg=COR_FUNDO, fg=COR_TEXTO,
        ).pack(pady=(28, 4))

        self.lbl_sub = tk.Label(
            self.root, text="Instalando dependências, aguarde...",
            font=("Segoe UI", 10),
            bg=COR_FUNDO, fg=COR_MUTED,
        )
        self.lbl_sub.pack(pady=(0, 14))

        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Azul.Horizontal.TProgressbar",
            troughcolor="#E5E7EB",
            background=COR_AZUL,
            bordercolor=COR_FUNDO,
            lightcolor=COR_AZUL,
            darkcolor=COR_AZUL,
        )
        self.progress = ttk.Progressbar(
            self.root, mode="indeterminate", length=430,
            style="Azul.Horizontal.TProgressbar",
        )
        self.progress.pack(pady=(0, 12))
        self.progress.start(10)

        frame = tk.Frame(self.root, bg=COR_FUNDO)
        frame.pack(fill="both", expand=True, padx=24)

        self.log = tk.Text(
            frame,
            font=("Consolas", 9),
            bg="#1F2937", fg="#D1FAE5",
            relief="flat", bd=0,
            state="disabled",
            height=8,
        )
        self.log.pack(fill="both", expand=True)

        self.lbl_status = tk.Label(
            self.root, text="",
            font=("Segoe UI", 10),
            bg=COR_FUNDO, fg=COR_MUTED,
        )
        self.lbl_status.pack(pady=(8, 20))

    def _centralizar(self, w, h):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    # ------------------------------------------------------------------
    # Helpers thread-safe
    # ------------------------------------------------------------------

    def _log(self, msg: str):
        def _do():
            self.log.configure(state="normal")
            self.log.insert("end", msg + "\n")
            self.log.see("end")
            self.log.configure(state="disabled")
        self.root.after(0, _do)

    def _status(self, msg: str, cor: str = COR_MUTED):
        self.root.after(0, lambda: self.lbl_status.configure(text=msg, fg=cor))

    def _sub(self, msg: str):
        self.root.after(0, lambda: self.lbl_sub.configure(text=msg))

    # ------------------------------------------------------------------
    # Instalação
    # ------------------------------------------------------------------

    def _run(self, cmd: list) -> int:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        for linha in proc.stdout:
            linha = linha.strip()
            if linha:
                self._log(linha)
        proc.wait()
        return proc.returncode

    def _instalar(self):
        try:
            self._sub("Instalando dependências, aguarde...")
            self._status("Instalando pacotes...")
            self._log("Iniciando instalação dos pacotes...")

            codigo = self._run([
                VENV_PY, "-m", "pip", "install",
                "--no-index", f"--find-links={PACOTES}",
                *PACOTES_LISTA,
            ])

            if codigo != 0:
                self._falha("Falha ao instalar pacotes. Verifique a pasta pacotes_automacao.")
                return

            self._sub("Criando atalho na área de trabalho...")
            self._status("Criando atalho...")
            self._log("Criando atalho...")
            self._run([VENV_PY, ATALHO_PY])

            self._sucesso = True
            self._log("Instalação concluída com sucesso!")
            self._sub("Pronto!")
            self._status("Instalação concluída!", COR_VERDE)
            self.progress.stop()

            self.root.after(1500, self.root.destroy)

        except Exception as e:
            self._falha(f"Erro inesperado: {e}")

    def _falha(self, msg: str):
        self._log(f"ERRO: {msg}")
        self._status(msg, COR_ERRO)
        self._sub("Instalação falhou.")
        self.progress.stop()
        # Libera o botão de fechar
        self.root.after(0, lambda: self.root.protocol("WM_DELETE_WINDOW", self.root.destroy))


if __name__ == "__main__":
    janela = JanelaInstalacao()
    sys.exit(0 if janela._sucesso else 1)
