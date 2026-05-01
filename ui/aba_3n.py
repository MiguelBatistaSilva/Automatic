"""
ui/aba_3n.py — Aba Automatic 3N: duplicacao de chamados sem Base de Conhecimento
"""
import csv
import io
import time

import pandas as pd

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QTextEdit, QComboBox,
    QPushButton, QGroupBox, QSizePolicy, QPlainTextEdit,
    QDialog,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QTextCharFormat, QFont

from ui.tema_qt import (
    COR_SUCESSO, COR_ERRO, COR_STATUS, COR_INFO, FONTE_MONO
)
from services.checkpoint import existe_pendente, resumo as resumo_checkpoint


# ---------------------------------------------------------------------------
# Dialog de Checkpoint (identico ao da aba principal)
# ---------------------------------------------------------------------------

class CheckpointDialog(QDialog):
    RETOMAR = 0
    DO_ZERO = 1

    def __init__(self, numero_chamado: str, resumo: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Checkpoint Encontrado")
        self.setMinimumWidth(420)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        lbl_titulo = QLabel("⏰  Execução anterior incompleta")
        lbl_titulo.setStyleSheet("font-size: 15px; font-weight: bold; color: #92400E;")
        layout.addWidget(lbl_titulo)

        lbl_chamado = QLabel(f"Chamado: <b>{numero_chamado}</b>")
        lbl_chamado.setStyleSheet("font-size: 13px; color: #374151;")
        layout.addWidget(lbl_chamado)

        lbl_resumo = QLabel(resumo)
        lbl_resumo.setStyleSheet(
            "font-size: 12px; color: #6B7280;"
            "background-color: #FEF9C3;"
            "border: 1px solid #D97706;"
            "border-radius: 5px;"
            "padding: 8px 12px;"
        )
        lbl_resumo.setWordWrap(True)
        layout.addWidget(lbl_resumo)

        btn_retomar = QPushButton("▶  Retomar de onde parou")
        btn_do_zero = QPushButton("🔄  Começar do zero")
        btn_retomar.setObjectName("btn_iniciar")
        btn_retomar.setFixedHeight(38)
        btn_do_zero.setObjectName("btn_secundario")
        btn_do_zero.setFixedHeight(38)
        btn_retomar.clicked.connect(self._retomar)
        btn_do_zero.clicked.connect(self._do_zero)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(btn_retomar)
        btn_layout.addWidget(btn_do_zero)
        layout.addLayout(btn_layout)

        self._escolha = self.RETOMAR

    def _retomar(self):
        self._escolha = self.RETOMAR
        self.accept()

    def _do_zero(self):
        self._escolha = self.DO_ZERO
        self.accept()

    @property
    def escolha(self) -> int:
        return self._escolha


# ---------------------------------------------------------------------------
# Worker thread
# ---------------------------------------------------------------------------

class Worker3N(QObject):
    log_signal = pyqtSignal(str, str)
    fim_signal = pyqtSignal(bool)

    def __init__(self, dados: dict, iniciar_do_zero: bool):
        super().__init__()
        self.dados = dados
        self.iniciar_do_zero = iniciar_do_zero

    def run(self):
        try:
            from services.automatic import _get_driver_manager
            from services.flow_3n import execute_3n_flow

            def log_func(msg, tipo="info"):
                self.log_signal.emit(msg, tipo)

            driver_manager = _get_driver_manager(log_func)
            driver = driver_manager.iniciar_driver_e_navegar()

            execute_3n_flow(
                driver         = driver,
                df             = self.dados["df"],
                descricao_base = self.dados["descricao_base"],
                numero_chamado = self.dados["numero_chamado"],
                usuario        = self.dados["usuario"],
                senha          = self.dados["senha"],
                log            = log_func,
                iniciar_do_zero= self.iniciar_do_zero,
            )
            self.fim_signal.emit(True)
        except Exception as e:
            self.log_signal.emit(f"Excecao inesperada: {e}", "error")
            self.fim_signal.emit(False)


# ---------------------------------------------------------------------------
# Aba 3N
# ---------------------------------------------------------------------------

class Aba3N(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.linhas_csv: list[list[str]] = []
        self.colunas_csv: list[str] = []
        self._thread = None
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # --- Duas colunas: config (esq) | CSV (dir) ---
        cols_layout = QHBoxLayout()
        cols_layout.setSpacing(24)

        # === Coluna Esquerda ===
        col_esq = QVBoxLayout()
        col_esq.setSpacing(6)

        col_esq.addWidget(QLabel("Chamado PAI"))
        self.input_chamado = QLineEdit()
        self.input_chamado.setPlaceholderText("Ex: S2123456 ou 2007909")
        col_esq.addWidget(self.input_chamado)

        cred_row = QHBoxLayout()
        cred_row.setSpacing(12)

        mat_col = QVBoxLayout()
        mat_col.setSpacing(4)
        mat_col.addWidget(QLabel("Matrícula"))
        self.input_usuario = QLineEdit()
        self.input_usuario.setPlaceholderText("Matrícula")
        mat_col.addWidget(self.input_usuario)
        cred_row.addLayout(mat_col)

        senha_col = QVBoxLayout()
        senha_col.setSpacing(4)
        senha_col.addWidget(QLabel("Senha"))
        self.input_senha = QLineEdit()
        self.input_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_senha.setPlaceholderText("Lanlink@")
        senha_col.addWidget(self.input_senha)
        cred_row.addLayout(senha_col)

        col_esq.addLayout(cred_row)

        col_esq.addWidget(QLabel("Descrição"))
        self.input_descricao = QLineEdit()
        self.input_descricao.setText("Solicito atualização de sistema...")
        col_esq.addWidget(self.input_descricao)

        # Botoes
        btn_layout = QHBoxLayout()
        self.btn_iniciar = QPushButton("▶  INICIAR")
        self.btn_iniciar.setObjectName("btn_iniciar")
        self.btn_iniciar.setFixedHeight(40)
        self.btn_iniciar.clicked.connect(self._iniciar)
        btn_layout.addWidget(self.btn_iniciar)

        self.btn_limpar = QPushButton("Limpar Logs")
        self.btn_limpar.setObjectName("btn_secundario")
        self.btn_limpar.clicked.connect(self._limpar_logs)
        btn_layout.addWidget(self.btn_limpar)
        btn_layout.addStretch()
        col_esq.addLayout(btn_layout)

        col_esq.addStretch()

        # === Coluna Direita ===
        col_dir = QVBoxLayout()
        col_dir.setSpacing(6)

        col_dir.addWidget(QLabel("Dados de Iteração"))
        self.txt_csv = QPlainTextEdit()
        self.txt_csv.setPlaceholderText(
            "Marca/Modelo,Tombo\n"
            "POSITIVO C6200,212150/323265\n"
            "HP ProBook 450,198342/411280"
        )
        self.txt_csv.setFont(QFont(FONTE_MONO, 11))
        col_dir.addWidget(self.txt_csv, 1)

        csv_btn_layout = QHBoxLayout()
        self.btn_importar = QPushButton("Importar dados")
        self.btn_importar.setObjectName("btn_secundario")
        self.btn_importar.clicked.connect(self._importar_csv)
        csv_btn_layout.addWidget(self.btn_importar)

        self.lbl_csv_status = QLabel("")
        self.lbl_csv_status.setStyleSheet(f"color: {COR_SUCESSO};")
        csv_btn_layout.addWidget(self.lbl_csv_status)
        csv_btn_layout.addStretch()
        col_dir.addLayout(csv_btn_layout)

        cols_layout.addLayout(col_esq, 1)
        cols_layout.addLayout(col_dir, 1)
        layout.addLayout(cols_layout, 1)

        # --- Logs ---
        grp_logs = QGroupBox("Registro de Execução")
        logs_layout = QVBoxLayout(grp_logs)
        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setFont(QFont(FONTE_MONO, 11))
        self.txt_logs.setMinimumHeight(200)
        logs_layout.addWidget(self.txt_logs)
        layout.addWidget(grp_logs, 1)

    def _importar_csv(self):
        texto = self.txt_csv.toPlainText().strip()
        if not texto:
            self.lbl_csv_status.setStyleSheet(f"color: {COR_ERRO};")
            self.lbl_csv_status.setText("Cole o CSV antes de importar.")
            return
        try:
            rows = list(csv.reader(io.StringIO(texto)))
            if not rows:
                raise ValueError("Nenhuma linha encontrada.")
            self.colunas_csv = [c.strip() for c in rows[0]]
            self.linhas_csv  = [
                [v.strip() for v in row]
                for row in rows[1:]
                if any(v.strip() for v in row)
            ]
            self.lbl_csv_status.setStyleSheet(f"color: {COR_SUCESSO};")
            self.lbl_csv_status.setText(
                f"✓ {len(self.linhas_csv)} linha(s), {len(self.colunas_csv)} coluna(s)"
            )
        except Exception as e:
            self.lbl_csv_status.setStyleSheet(f"color: {COR_ERRO};")
            self.lbl_csv_status.setText(f"Erro: {e}")

    def _iniciar(self):
        erros = []
        if not self.linhas_csv:
            erros.append("Importe o CSV antes de iniciar.")
        if not self.input_chamado.text().strip():
            erros.append("Preencha o numero do Chamado PAI.")
        if not self.input_usuario.text().strip():
            erros.append("Preencha a matricula.")
        if not self.input_senha.text().strip():
            erros.append("Preencha a senha.")

        if erros:
            for e in erros:
                self._append_log(e, "error")
            return

        numero_chamado = self.input_chamado.text().strip()

        # --- Verificar checkpoint via dialog ---
        iniciar_do_zero = False
        if existe_pendente(numero_chamado):
            resumo = resumo_checkpoint(numero_chamado)
            dialog = CheckpointDialog(numero_chamado, resumo, parent=self)
            dialog.exec()
            iniciar_do_zero = (dialog.escolha == CheckpointDialog.DO_ZERO)

        dados = {
            "descricao_base": self.input_descricao.text(),
            "df":             pd.DataFrame(self.linhas_csv, columns=self.colunas_csv),
            "numero_chamado": numero_chamado,
            "usuario":        self.input_usuario.text().strip(),
            "senha":          self.input_senha.text().strip(),
        }

        self._set_em_execucao(True)

        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait()

        self._worker = Worker3N(dados, iniciar_do_zero)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.log_signal.connect(self._append_log)
        self._worker.fim_signal.connect(self._fim_execucao)
        self._worker.fim_signal.connect(self._thread.quit)
        self._thread.start()

    def _fim_execucao(self, sucesso: bool):
        if sucesso:
            self._append_log("Fluxo 3N concluido com sucesso.", "success")
        else:
            self._append_log("Fluxo 3N encerrado com falha. Verifique os logs.", "error")
        self._set_em_execucao(False)

    def _set_em_execucao(self, em_exec: bool):
        self.btn_iniciar.setEnabled(not em_exec)
        self.btn_iniciar.setText("⏳ EM ANDAMENTO..." if em_exec else "▶  INICIAR")
        self.input_chamado.setEnabled(not em_exec)
        self.input_usuario.setEnabled(not em_exec)
        self.input_senha.setEnabled(not em_exec)
        self.txt_csv.setEnabled(not em_exec)

    def _limpar_logs(self):
        self.txt_logs.clear()

    def _append_log(self, mensagem: str, tipo: str = "info"):
        ts     = time.strftime("%H:%M:%S")
        labels = {"info": "INFO", "status": "STATUS", "success": "SUCESSO", "error": "ERRO"}
        label  = labels.get(tipo, tipo.upper())
        linha  = f"[{ts}] [{label}] {mensagem}"

        cores = {
            "success": COR_SUCESSO,
            "error":   COR_ERRO,
            "status":  COR_STATUS,
            "info":    COR_INFO,
        }
        cor    = cores.get(tipo, COR_INFO)
        fmt    = QTextCharFormat()
        fmt.setForeground(QColor(cor))
        cursor = self.txt_logs.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(linha + "\n", fmt)
        self.txt_logs.setTextCursor(cursor)
        self.txt_logs.ensureCursorVisible()