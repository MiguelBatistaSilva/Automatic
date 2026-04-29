import time

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton, QGroupBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QTextCharFormat, QFont

from ui.tema_qt import COR_SUCESSO, COR_ERRO, COR_STATUS, COR_INFO, FONTE_MONO

_URL_HOME = "https://cati.tjce.jus.br/assystweb/application.do"


# ---------------------------------------------------------------------------
# Worker thread — tenta login em loop até entrar ou credencial inválida
# ---------------------------------------------------------------------------

class LicenseWorker(QObject):
    log_signal = pyqtSignal(str, str)
    fim_signal = pyqtSignal(bool)

    def __init__(self, usuario: str, senha: str):
        super().__init__()
        self.usuario = usuario
        self.senha = senha

    def run(self):
        try:
            from services.automatic import _get_driver_manager
            from selenium.webdriver.common.by import By

            def log(msg, tipo="info"):
                self.log_signal.emit(msg, tipo)

            driver_manager = _get_driver_manager(log)
            driver = driver_manager.iniciar_driver_e_navegar()

            while True:
                driver.get(_URL_HOME)
                time.sleep(0.5)

                # Sessão já ativa
                if (not driver.find_elements(By.ID, "login-user")
                        and "application.do" in driver.current_url
                        and not driver.find_elements(By.CSS_SELECTOR, "ol.axios-logout-error")):
                    log("✅ Sessão ativa — login já realizado!", "success")
                    self.fim_signal.emit(True)
                    return

                try:
                    user_field = driver.find_element(By.ID, "login-user")
                    user_field.clear()
                    user_field.send_keys(self.usuario)

                    pass_field = driver.find_element(By.ID, "login-password")
                    pass_field.clear()
                    pass_field.send_keys(self.senha)

                    driver.find_element(By.ID, "loginSubmit").click()
                except Exception:
                    pass

                time.sleep(1)

                # Credencial errada — para imediatamente
                erro_cred = driver.find_elements(By.CSS_SELECTOR, "ol.errormsg")
                if erro_cred and erro_cred[0].is_displayed():
                    log(f"❌ Credencial inválida: {erro_cred[0].text}", "error")
                    self.fim_signal.emit(False)
                    return

                # Licença cheia — tenta de novo
                erro_lic = driver.find_elements(By.CSS_SELECTOR, "ol.axios-logout-error")
                if erro_lic and erro_lic[0].is_displayed():
                    log("⏳ Licença cheia. Retentando...", "status")
                    continue

                # Sucesso
                if not driver.find_elements(By.ID, "login-user"):
                    log("✅ Login realizado com sucesso!", "success")
                    self.fim_signal.emit(True)
                    return

        except Exception as e:
            self.log_signal.emit(f"Exceção inesperada: {e}", "error")
            self.fim_signal.emit(False)


# ---------------------------------------------------------------------------
# Aba License
# ---------------------------------------------------------------------------

class AbaLicense(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = None
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # --- Campos de credencial + botões na mesma linha ---
        cred_layout = QHBoxLayout()
        cred_layout.setSpacing(10)

        def _lbl(texto):
            lbl = QLabel(texto)
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return lbl

        cred_layout.addWidget(_lbl("Matrícula"))
        self.input_usuario = QLineEdit()
        self.input_usuario.setPlaceholderText("400123")
        self.input_usuario.setMinimumWidth(120)
        self.input_usuario.setMaximumWidth(160)
        cred_layout.addWidget(self.input_usuario)

        cred_layout.addWidget(_lbl("Senha"))
        self.input_senha = QLineEdit()
        self.input_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_senha.setPlaceholderText("Lanlink@")
        self.input_senha.setMinimumWidth(120)
        self.input_senha.setMaximumWidth(160)
        cred_layout.addWidget(self.input_senha)

        self.btn_iniciar = QPushButton("▶  INICIAR")
        self.btn_iniciar.setObjectName("btn_iniciar")
        self.btn_iniciar.setFixedHeight(40)
        self.btn_iniciar.clicked.connect(self._iniciar)
        cred_layout.addWidget(self.btn_iniciar)

        cred_layout.addStretch()
        layout.addLayout(cred_layout)

        # --- Logs ---
        grp_logs = QGroupBox("Registro de Tentativas")
        logs_layout = QVBoxLayout(grp_logs)
        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setFont(QFont(FONTE_MONO, 11))
        logs_layout.addWidget(self.txt_logs)
        layout.addWidget(grp_logs, 1)

    def _iniciar(self):
        usuario = self.input_usuario.text().strip()
        senha = self.input_senha.text().strip()

        if not usuario or not senha:
            self._append_log("Preencha matrícula e senha antes de iniciar.", "error")
            return

        self._set_em_execucao(True)
        self._worker = LicenseWorker(usuario, senha)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.log_signal.connect(self._append_log)
        self._worker.fim_signal.connect(self._fim)
        self._worker.fim_signal.connect(self._thread.quit)
        self._thread.start()

    def _fim(self, sucesso: bool):
        self._set_em_execucao(False)

    def _set_em_execucao(self, em_exec: bool):
        self.btn_iniciar.setEnabled(not em_exec)
        self.btn_iniciar.setText("⏳ EM ANDAMENTO..." if em_exec else "▶  INICIAR")
        self.input_usuario.setEnabled(not em_exec)
        self.input_senha.setEnabled(not em_exec)

    def _append_log(self, mensagem: str, tipo: str = "info"):
        import time as _time
        ts = _time.strftime("%H:%M:%S")
        labels = {"info": "INFO", "status": "STATUS", "success": "SUCESSO", "error": "ERRO"}
        label = labels.get(tipo, tipo.upper())
        linha = f"[{ts}] [{label}] {mensagem}"

        cores = {"success": COR_SUCESSO, "error": COR_ERRO, "status": COR_STATUS, "info": COR_INFO}
        cor = cores.get(tipo, COR_INFO)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(cor))
        cursor = self.txt_logs.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(linha + "\n", fmt)
        self.txt_logs.setTextCursor(cursor)
        self.txt_logs.ensureCursorVisible()
