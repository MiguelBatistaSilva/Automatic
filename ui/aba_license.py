from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTextEdit, QPushButton, QGroupBox,
)
from PyQt6.QtCore import QThread, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QTextCharFormat, QFont

from ui.tema_qt import COR_SUCESSO, COR_ERRO, COR_STATUS, COR_INFO, FONTE_MONO
from ui.dialog_credenciais import obter_credenciais

# A URL de login vive em services/flow_utils.py (_URL_HOME) e chega aqui via
# browser_pw, para nao existirem duas copias divergindo.


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
            from services.browser_pw import NavegadorPW, _fazer_login_pw

            def log(msg, tipo="info"):
                self.log_signal.emit(msg, tipo)

            # manter_aberto=True: o proposito desta aba e segurar a sessao. O
            # navegador fica aberto quando o worker termina, para o usuario
            # trabalhar manualmente — nao ha fluxo automatizado depois daqui.
            with NavegadorPW(log, manter_aberto=True) as page:
                # _fazer_login_pw ja e o "login infinito": ele repete enquanto o
                # Assyst responder que as licencas estao em uso, e so desiste se
                # a credencial for invalida.
                ok = _fazer_login_pw(page, self.usuario, self.senha, log)
                if ok:
                    log("✅ Sessão garantida. O navegador ficou aberto para uso manual.",
                        "success")
                else:
                    log("❌ Nao foi possivel logar. Verifique as credenciais no "
                        "menu ⓘ → Credenciais.", "error")
                self.fim_signal.emit(ok)

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

        # Credenciais nao ficam mais aqui: sao unicas para o app inteiro e vivem
        # no menu ⓘ → Credenciais (ui/dialog_credenciais.py).

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
        cred = obter_credenciais(self)
        if cred is None:
            self._append_log("Credenciais nao cadastradas.", "error")
            return
        usuario, senha = cred

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
