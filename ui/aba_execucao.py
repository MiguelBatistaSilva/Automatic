import time
import csv
import io
import pandas as pd

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QTextEdit, QComboBox,
    QPushButton, QGroupBox, QSizePolicy, QPlainTextEdit,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QTextCharFormat, QFont

from ui.tema_qt import (
    COR_SUCESSO, COR_ERRO, COR_STATUS, COR_INFO, COR_TEXTO, FONTE_MONO
)


# ---------------------------------------------------------------------------
# Worker thread — roda o Selenium sem travar a UI
# ---------------------------------------------------------------------------

class AutomacaoWorker(QObject):
    log_signal   = pyqtSignal(str, str)
    fim_signal   = pyqtSignal(bool)

    def __init__(self, dados: dict):
        super().__init__()
        self.dados = dados

    def run(self):
        try:
            from services.automatic import Automatic

            def log_func(msg, type_log="info"):
                self.log_signal.emit(msg, type_log)

            orchestrator = Automatic(log_func)
            resultado = orchestrator.executar_fluxo(self.dados)
            self.fim_signal.emit(resultado)
        except Exception as e:
            self.log_signal.emit(f"Excecao inesperada: {e}", "error")
            self.fim_signal.emit(False)


# ---------------------------------------------------------------------------
# Aba de Execucao
# ---------------------------------------------------------------------------

class AbaExecucao(QWidget):

    def __init__(self, kb_entries: list, parent=None):
        super().__init__(parent)
        self.kb_entries = kb_entries
        self.linhas_csv: list[list[str]] = []
        self.colunas_csv: list[str] = []
        self._thread = None
        self._worker = None
        self._setup_ui()

    def atualizar_kbs(self, entries: list):
        self.kb_entries = entries
        self.combo_kb.clear()
        for e in entries:
            self.combo_kb.addItem(e["nome_artigo"])

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # --- Topo: duas colunas (config | csv) ---
        top_layout = QHBoxLayout()
        top_layout.setSpacing(20)

        # Coluna esquerda — campos de configuracao
        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setColumnStretch(1, 3)
        grid.setColumnStretch(3, 2)
        grid.setColumnStretch(5, 2)

        def _lbl(texto):
            lbl = QLabel(texto)
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return lbl

        grid.addWidget(_lbl("Referência"), 0, 0)
        self.input_chamado = QLineEdit()
        self.input_chamado.setPlaceholderText("Ex: S2123456 ou 2012380")
        self.input_chamado.setMinimumWidth(160)
        grid.addWidget(self.input_chamado, 0, 1)

        grid.addWidget(_lbl("Matrícula"), 0, 2)
        self.input_usuario = QLineEdit()
        self.input_usuario.setPlaceholderText("400123")
        self.input_usuario.setMinimumWidth(120)
        grid.addWidget(self.input_usuario, 0, 3)

        grid.addWidget(_lbl("Senha"), 0, 4)
        self.input_senha = QLineEdit()
        self.input_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_senha.setPlaceholderText("Lanlink@")
        self.input_senha.setMinimumWidth(120)
        grid.addWidget(self.input_senha, 0, 5)

        grid.addWidget(_lbl("Descrição"), 1, 0)
        self.input_descricao = QLineEdit()
        self.input_descricao.setText("Solicito atualização de sistema...")
        grid.addWidget(self.input_descricao, 1, 1, 1, 5)

        grid.addWidget(_lbl("Base de Conhecimento"), 2, 0)
        self.combo_kb = QComboBox()
        self.combo_kb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for e in self.kb_entries:
            self.combo_kb.addItem(e["nome_artigo"])
        grid.addWidget(self.combo_kb, 2, 1, 1, 5)

        left_widget = QWidget()
        left_widget.setLayout(grid)
        top_layout.addWidget(left_widget, 2)

        # Coluna direita — Dados de Iteracao
        right_layout = QVBoxLayout()
        right_layout.setSpacing(6)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_titulo_csv = QLabel("Dados de Iteração")
        self.lbl_titulo_csv.setObjectName("label_secao")
        self.lbl_titulo_csv.setStyleSheet("text-transform: none;")
        right_layout.addWidget(self.lbl_titulo_csv)

        self.txt_csv = QPlainTextEdit()
        self.txt_csv.setPlaceholderText(
            "Marca/Modelo,Tombo\n"
            "POSITIVO C6200,212150/323265\n"
            "HP ProBook 450,198342/411280"
        )
        self.txt_csv.setFixedHeight(100)
        self.txt_csv.setFont(QFont(FONTE_MONO, 11))
        right_layout.addWidget(self.txt_csv)

        csv_btn_layout = QHBoxLayout()
        self.btn_importar = QPushButton("Importar CSV")
        self.btn_importar.setObjectName("btn_secundario")
        self.btn_importar.clicked.connect(self._importar_csv)
        csv_btn_layout.addWidget(self.btn_importar)

        self.lbl_csv_status = QLabel("")
        self.lbl_csv_status.setStyleSheet(f"color: {COR_SUCESSO};")
        csv_btn_layout.addWidget(self.lbl_csv_status)
        csv_btn_layout.addStretch()
        right_layout.addLayout(csv_btn_layout)
        right_layout.addStretch()

        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        top_layout.addWidget(right_widget, 1)

        layout.addLayout(top_layout)

        # --- Botoes de acao ---
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
        layout.addLayout(btn_layout)

        # --- Logs (stretch=1 para preencher o espaco restante) ---
        grp_logs = QGroupBox("Registro de Execucao")
        logs_layout = QVBoxLayout(grp_logs)
        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setFont(QFont(FONTE_MONO, 11))
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
            self.linhas_csv = [[v.strip() for v in row] for row in rows[1:] if any(v.strip() for v in row)]
            self.lbl_csv_status.setStyleSheet(f"color: {COR_SUCESSO};")
            self.lbl_csv_status.setText(f"✓ {len(self.linhas_csv)} linha(s), {len(self.colunas_csv)} coluna(s)")
        except Exception as e:
            self.lbl_csv_status.setStyleSheet(f"color: {COR_ERRO};")
            self.lbl_csv_status.setText(f"Erro: {e}")

    def _iniciar(self):
        erros = []
        if not self.linhas_csv:
            erros.append("Importe o CSV antes de iniciar.")
        if self.combo_kb.currentIndex() < 0 or not self.combo_kb.currentText():
            erros.append("Selecione uma Base de Conhecimento.")
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

        kb_nome = self.combo_kb.currentText()
        kb_entry = next((e for e in self.kb_entries if e["nome_artigo"] == kb_nome), None)
        if not kb_entry:
            self._append_log("Base de Conhecimento nao encontrada.", "error")
            return

        dados = {
            "descricao_base": self.input_descricao.text(),
            "kb_config":      {"keyword": kb_entry["keyword"], "nome_artigo": kb_entry["nome_artigo"]},
            "df":             pd.DataFrame(self.linhas_csv, columns=self.colunas_csv),
            "numero_chamado": self.input_chamado.text().strip(),
            "usuario":        self.input_usuario.text().strip(),
            "senha":          self.input_senha.text().strip(),
        }

        self._set_em_execucao(True)
        self._worker = AutomacaoWorker(dados)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.log_signal.connect(self._append_log)
        self._worker.fim_signal.connect(self._fim_execucao)
        self._worker.fim_signal.connect(self._thread.quit)
        self._thread.start()

    def _fim_execucao(self, sucesso: bool):
        if sucesso:
            self._append_log("Fluxo concluido com sucesso.", "success")
        else:
            self._append_log("Fluxo encerrado com falha. Verifique os logs.", "error")
        self._set_em_execucao(False)

    def _set_em_execucao(self, em_exec: bool):
        self.btn_iniciar.setEnabled(not em_exec)
        self.btn_iniciar.setText("⏳ EM ANDAMENTO..." if em_exec else "▶  INICIAR")
        self.input_chamado.setEnabled(not em_exec)
        self.input_usuario.setEnabled(not em_exec)
        self.input_senha.setEnabled(not em_exec)
        self.combo_kb.setEnabled(not em_exec)
        self.txt_csv.setEnabled(not em_exec)

    def _limpar_logs(self):
        self.txt_logs.clear()

    def _append_log(self, mensagem: str, tipo: str = "info"):
        ts = time.strftime("%H:%M:%S")
        labels = {"info": "INFO", "status": "STATUS", "success": "SUCESSO", "error": "ERRO"}
        label = labels.get(tipo, tipo.upper())
        linha = f"[{ts}] [{label}] {mensagem}"

        cores = {
            "success": COR_SUCESSO,
            "error":   COR_ERRO,
            "status":  COR_STATUS,
            "info":    COR_INFO,
        }
        cor = cores.get(tipo, COR_INFO)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(cor))
        cursor = self.txt_logs.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(linha + "\n", fmt)
        self.txt_logs.setTextCursor(cursor)
        self.txt_logs.ensureCursorVisible()
