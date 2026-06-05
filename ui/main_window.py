from PyQt6.QtWidgets import QMainWindow, QTabWidget, QStatusBar, QToolButton, QMenu
from PyQt6.QtGui import QIcon, QGuiApplication, QDesktopServices
from PyQt6.QtCore import QUrl
from ui.aba_execucao import AbaExecucao
from ui.aba_kb import AbaKB
from ui.aba_license import AbaLicense
from ui.aba_sla import AbaSLA


class MainWindow(QMainWindow):

    def __init__(self, kb_store, icon_path: str = ""):
        super().__init__()
        self.setWindowTitle("Automatic v6.2.3")
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
        self.aba_sla     = AbaSLA()
        self.aba_license = AbaLicense()
        self.aba_kb      = AbaKB(kb_store)

        self.tabs.addTab(self.aba_exec,    "🤖 Desmembramento")
        self.tabs.addTab(self.aba_sla,     "⏱️ Análise de SLA")
        self.tabs.addTab(self.aba_license, "🔑 License")
        self.tabs.addTab(self.aba_kb,      "📚 Bases de Conhecimento")

        self.aba_kb.kbs_atualizadas.connect(self.aba_exec.atualizar_kbs)

        self.tabs.setCornerWidget(self._criar_btn_links())

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Pronto.")

    def _criar_btn_links(self) -> QToolButton:
        _URL_LINKS  = "https://recondite-frog-e5d.notion.site/Bem-vindo-2e6e32b25a248027b36ef626bf484553"

        menu = QMenu(self)
        menu.addAction("🔗  Sobre",    lambda: QDesktopServices.openUrl(QUrl(_URL_LINKS)))

        btn = QToolButton(self)
        btn.setText("ⓘ")
        btn.setMenu(menu)
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        return btn