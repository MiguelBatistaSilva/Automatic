from PyQt6.QtWidgets import QMainWindow, QTabWidget, QStatusBar, QToolButton, QMenu
from PyQt6.QtGui import QIcon, QGuiApplication, QDesktopServices
from PyQt6.QtCore import QUrl

from ui.aba_execucao import AbaExecucao
from ui.aba_kb import AbaKB
from ui.aba_license import AbaLicense


class MainWindow(QMainWindow):

    def __init__(self, kb_store, icon_path: str = ""):
        super().__init__()
        self.setWindowTitle("Automatic v6.0")
        self.setMinimumSize(900, 700)
        self.resize(1200, 700)

        screen = QGuiApplication.primaryScreen().availableGeometry()
        size = self.geometry()
        x = (screen.width() - size.width()) // 2
        y = (screen.height() - size.height()) // 2
        self.move(x, y)

        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        entries = kb_store.carregar()

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.aba_exec    = AbaExecucao(entries)
        self.aba_license = AbaLicense()
        self.aba_kb      = AbaKB(kb_store)

        self.tabs.addTab(self.aba_exec,    "🤖 Automatic")
        self.tabs.addTab(self.aba_license, "🔑 License")
        self.tabs.addTab(self.aba_kb,      "📚 Bases de Conhecimento")

        self.aba_kb.kbs_atualizadas.connect(self.aba_exec.atualizar_kbs)

        self.tabs.setCornerWidget(self._criar_btn_links())

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Pronto.")

    def _criar_btn_links(self) -> QToolButton:
        _URL_LINKEDIN  = "http://linkedin.com/in/miguel-batista-silva"
        _URL_GITHUB    = "https://github.com/MiguelBatistaSilva"
        _URL_HF        = "https://huggingface.co/MiguelBS"
        _URL_CURRICULO = "https://recondite-frog-e5d.notion.site/Miguel-Batista-208e32b25a24808e9d79e8d347db3c30?source=copy_link"

        menu = QMenu(self)
        menu.addAction("🔗  LinkedIn",  lambda: QDesktopServices.openUrl(QUrl(_URL_LINKEDIN)))
        menu.addAction("😺  GitHub",    lambda: QDesktopServices.openUrl(QUrl(_URL_GITHUB)))
        menu.addAction("🤗  HuggingFace", lambda: QDesktopServices.openUrl(QUrl(_URL_HF)))
        menu.addAction("📄  Currículo", lambda: QDesktopServices.openUrl(QUrl(_URL_CURRICULO)))

        btn = QToolButton(self)
        btn.setText("ⓘ")
        btn.setMenu(menu)
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        return btn
