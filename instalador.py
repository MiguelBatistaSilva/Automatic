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
ICONE     = os.path.join(BASE_DIR, "app_icon.ico")

PACOTES_LISTA = ["pandas", "selenium", "PyQt6", "pywin32", "requests",
                 "playwright", "keyring"]

# Paleta clara, alinhada ao tema do app (ui/tema_qt.py).
COR_FUNDO    = "#FFFFFF"
COR_TEXTO    = "#111827"
COR_MUTED    = "#6B7280"
COR_VERDE    = "#16A34A"
COR_ERRO     = "#DC2626"
COR_AZUL     = "#2563EB"
COR_BORDA    = "#D1D5DB"
COR_LOG_BG   = "#F9FAFB"
COR_LOG_TXT  = "#374151"
COR_TRILHA   = "#E5E7EB"


class JanelaInstalacao:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Configurando Automatic")
        self.root.resizable(False, False)
        self.root.configure(bg=COR_FUNDO)
        self._sucesso = False

        # Substitui o icone padrao do Tk (a "pena") pelo icone do app.
        try:
            self.root.iconbitmap(ICONE)
        except Exception:
            pass

        self._build_ui()
        self._centralizar(500, 380)

        # Impede fechar durante a instalação
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)

        threading.Thread(target=self._instalar, daemon=True).start()
        self.root.mainloop()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        # ── Cabecalho ──────────────────────────────────────────────────
        header = tk.Frame(self.root, bg=COR_FUNDO)
        header.pack(fill="x", padx=28, pady=(26, 0))

        tk.Label(
            header, text="Configurando o Automatic",
            font=("Segoe UI", 15, "bold"),
            bg=COR_FUNDO, fg=COR_TEXTO, anchor="w",
        ).pack(fill="x")

        self.lbl_sub = tk.Label(
            header, text="Instalando dependências, aguarde...",
            font=("Segoe UI", 10),
            bg=COR_FUNDO, fg=COR_MUTED, anchor="w",
        )
        self.lbl_sub.pack(fill="x", pady=(2, 0))

        # ── Barra de progresso ─────────────────────────────────────────
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Azul.Horizontal.TProgressbar",
            troughcolor=COR_TRILHA,
            background=COR_AZUL,
            bordercolor=COR_FUNDO,
            lightcolor=COR_AZUL,
            darkcolor=COR_AZUL,
            thickness=8,
        )
        self.progress = ttk.Progressbar(
            self.root, mode="indeterminate", length=444,
            style="Azul.Horizontal.TProgressbar",
        )
        self.progress.pack(padx=28, pady=(16, 14))
        self.progress.start(10)

        # ── Card de log (tema claro com borda) ─────────────────────────
        log_border = tk.Frame(self.root, bg=COR_BORDA)
        log_border.pack(fill="both", expand=True, padx=28)

        self.log = tk.Text(
            log_border,
            font=("Consolas", 9),
            bg=COR_LOG_BG, fg=COR_LOG_TXT,
            relief="flat", bd=0, highlightthickness=0,
            padx=10, pady=8,
            state="disabled",
            height=8,
        )
        self.log.pack(fill="both", expand=True, padx=1, pady=1)

        # ── Status ─────────────────────────────────────────────────────
        self.lbl_status = tk.Label(
            self.root, text="",
            font=("Segoe UI", 10, "bold"),
            bg=COR_FUNDO, fg=COR_MUTED, anchor="w",
        )
        self.lbl_status.pack(fill="x", padx=28, pady=(10, 22))

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
