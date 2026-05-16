from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar,
)
from PyQt6.QtCore import Qt
from services.updater import UpdateDownloader, aplicar_atualizacao


class UpdateDialog(QDialog):
    def __init__(self, versao_remota: str, download_url: str, parent=None):
        super().__init__(parent)
        self.versao_remota = versao_remota
        self.download_url = download_url
        self.app_dir = str(Path(__file__).parent.parent)
        self._worker = None

        self.setWindowTitle("Atualização disponível")
        self.setFixedWidth(420)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        self.label = QLabel(
            f"Há uma nova versão do Automatic disponível: <b>v{versao_remota}</b>.<br><br>"
            "Deseja instalar agora?"
        )
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.hide()
        layout.addWidget(self.progress)

        btns = QHBoxLayout()
        self.btn_instalar = QPushButton("Instalar")
        self.btn_agora_nao = QPushButton("Agora não")
        self.btn_instalar.clicked.connect(self._instalar)
        self.btn_agora_nao.clicked.connect(self.reject)
        btns.addWidget(self.btn_instalar)
        btns.addWidget(self.btn_agora_nao)
        layout.addLayout(btns)

    def _instalar(self):
        self.btn_instalar.setEnabled(False)
        self.btn_agora_nao.setEnabled(False)
        self.label.setText("Baixando atualização...")
        self.progress.show()
        self.adjustSize()

        self._worker = UpdateDownloader(self.download_url, self.app_dir)
        self._worker.progresso.connect(self.progress.setValue)
        self._worker.concluido.connect(self._aplicar)
        self._worker.erro.connect(self._on_erro)
        self._worker.start()

    def _aplicar(self, pasta_extraida: str):
        self.label.setText("Aplicando atualização. O aplicativo será reiniciado...")
        aplicar_atualizacao(pasta_extraida, self.app_dir)
        QApplication.quit()

    def _on_erro(self, msg: str):
        self.label.setText(f"Erro ao baixar atualização:\n{msg}")
        self.btn_agora_nao.setEnabled(True)
        self.btn_agora_nao.setText("Fechar")
        self.progress.hide()
        self.adjustSize()
