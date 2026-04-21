import sys
import os
import ctypes

# Garante que o diretorio raiz esta no path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from ui.main_window import MainWindow
from ui.tema_qt import ESTILO_GLOBAL
from services.kb_store import carregar, salvar

# Cria um objeto compativel com o kb_store
class KBStore:
    def carregar(self): return carregar()
    def salvar(self, entries): salvar(entries)


def main():
    # Define o AppUserModelID para o Windows exibir o icone correto na barra de tarefas
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("CATI.Automacao.6")

    app = QApplication(sys.argv)
    app.setApplicationName("Automatic v6.0")
    app.setStyleSheet(ESTILO_GLOBAL)

    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_icon.ico")
    app.setWindowIcon(QIcon(icon_path))

    kb_store = KBStore()
    window = MainWindow(kb_store, icon_path)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
