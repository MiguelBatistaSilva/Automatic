import sys
import os
import ctypes

# Deve ser chamado antes de qualquer import do Qt para garantir que o Windows
# associe o icone correto na barra de tarefas desde o primeiro handle criado.
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("CATI.Automacao.6")

# Garante que o diretorio raiz esta no path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QTimer

from ui.main_window import MainWindow
from ui.tema_qt import ESTILO_GLOBAL
from services.kb_store import carregar, salvar
from version import VERSION
from services.updater import UpdateChecker
from ui.update_dialog import UpdateDialog

# Cria um objeto compativel com o kb_store
class KBStore:
    def carregar(self): return carregar()
    def salvar(self, entries): salvar(entries)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Automatic v6.2.3")
    app.setStyleSheet(ESTILO_GLOBAL)

    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_icon.ico")
    app.setWindowIcon(QIcon(icon_path))

    kb_store = KBStore()
    window = MainWindow(kb_store, icon_path)
    window.show()

    # Reaplica o icone apos o show(): o HWND e o botao da barra de tarefas ja
    # existem, entao este WM_SETICON pega o botao "vivo" e evita o race da
    # primeira execucao (cache de icone frio do Windows por AppUserModelID).
    QTimer.singleShot(0, lambda: window.setWindowIcon(QIcon(icon_path)))

    checker = UpdateChecker(VERSION)
    checker.nova_versao.connect(lambda v, url: UpdateDialog(v, url, window).exec())
    checker.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
