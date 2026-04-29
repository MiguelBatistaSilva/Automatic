"""
ui/aba_execucao.py — Aba principal de execucao da automacao
"""
import csv
import io
import time

import pandas as pd

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QTextEdit, QComboBox,
    QPushButton, QGroupBox, QSizePolicy, QPlainTextEdit,
    QCheckBox, QFrame,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QTextCharFormat, QFont

from ui.tema_qt import (
    COR_SUCESSO, COR_ERRO, COR_STATUS, COR_INFO,
    COR_TEXTO, COR_AVISO, FONTE_MONO
)
from services.checkpoint import existe_pendente, resumo as resumo_checkpoint


# ---------------------------------------------------------------------------
# Worker thread
# ---------------------------------------------------------------------------

class AutomacaoWorker(QObject):
    log_signal = pyqtSignal(str, str)
    fim_signal = pyqtSignal(bool)

    def __init__(self, dados: dict, iniciar_do_zero: bool):
        super().__init__()
        self.dados = dados
        self.iniciar_do_zero = iniciar_do_zero

    def run(self):
        try:
            from services.automatic import Automatic

            def log_func(msg, type_log="info"):
                self.log_signal.emit(msg, type_log)

            orchestrator = Automatic(log_func)
            resultado = orchestrator.executar_fluxo(
                self.dados,
                iniciar_do_zero=self.iniciar_do_zero,
            )
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
        self.input_chamado.textChanged.connect(self._verificar_checkpoint)
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

        col_esq.addWidget(QLabel("Base de Conhecimento"))
        self.combo_kb = QComboBox()
        self.combo_kb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for e in self.kb_entries:
            self.combo_kb.addItem(e["nome_artigo"])
        col_esq.addWidget(self.combo_kb)

        # Aviso de Checkpoint
        self.frame_checkpoint = QFrame()
        self.frame_checkpoint.setStyleSheet("""
            QFrame {
                background-color: #FEF9C3;
                border: 1px solid #D97706;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        cp_layout = QVBoxLayout(self.frame_checkpoint)
        cp_layout.setContentsMargins(10, 8, 10, 8)
        cp_layout.setSpacing(6)

        self.lbl_checkpoint = QLabel("")
        self.lbl_checkpoint.setStyleSheet("color: #92400E; font-weight: bold; border: none;")
        cp_layout.addWidget(self.lbl_checkpoint)

        self.chk_do_zero = QCheckBox("Ignorar checkpoint e comecar do zero")
        self.chk_do_zero.setStyleSheet("color: #78350F; border: none;")
        cp_layout.addWidget(self.chk_do_zero)

        self.frame_checkpoint.setVisible(False)
        col_esq.addWidget(self.frame_checkpoint)

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

        # --- Logs (largura total) ---
        grp_logs = QGroupBox("Registro de Execução")
        logs_layout = QVBoxLayout(grp_logs)
        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setFont(QFont(FONTE_MONO, 11))
        self.txt_logs.setMinimumHeight(200)
        logs_layout.addWidget(self.txt_logs)
        layout.addWidget(grp_logs, 1)

    def _verificar_checkpoint(self, numero: str):
        numero = numero.strip()
        if not numero:
            self.frame_checkpoint.setVisible(False)
            return

        if existe_pendente(numero):
            info = resumo_checkpoint(numero)
            self.lbl_checkpoint.setText(f"⏰  {info}")
            self.chk_do_zero.setChecked(False)
            self.frame_checkpoint.setVisible(True)
        else:
            self.frame_checkpoint.setVisible(False)

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
        if self.combo_kb.currentIndex() < 0:
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

        kb_nome  = self.combo_kb.currentText()
        kb_entry = next((e for e in self.kb_entries if e["nome_artigo"] == kb_nome), None)
        if not kb_entry:
            self._append_log("Base de Conhecimento nao encontrada.", "error")
            return

        iniciar_do_zero = self.chk_do_zero.isChecked()

        dados = {
            "descricao_base": self.input_descricao.text(),
            "kb_config":      {"keyword": kb_entry["keyword"], "nome_artigo": kb_entry["nome_artigo"]},
            "df":             pd.DataFrame(self.linhas_csv, columns=self.colunas_csv),
            "numero_chamado": self.input_chamado.text().strip(),
            "usuario":        self.input_usuario.text().strip(),
            "senha":          self.input_senha.text().strip(),
        }

        self._set_em_execucao(True)
        self._worker = AutomacaoWorker(dados, iniciar_do_zero)
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
        # Atualizar aviso de checkpoint
        self._verificar_checkpoint(self.input_chamado.text())

    def _set_em_execucao(self, em_exec: bool):
        self.btn_iniciar.setEnabled(not em_exec)
        self.btn_iniciar.setText("⏳ EM ANDAMENTO..." if em_exec else "▶  INICIAR")
        self.input_chamado.setEnabled(not em_exec)
        self.input_usuario.setEnabled(not em_exec)
        self.input_senha.setEnabled(not em_exec)
        self.combo_kb.setEnabled(not em_exec)
        self.txt_csv.setEnabled(not em_exec)
        self.chk_do_zero.setEnabled(not em_exec)

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