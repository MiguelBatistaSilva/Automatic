"""
ui/aba_execucao.py — Aba principal de execucao da automacao
Modos via QComboBox:
  0 - Criar + Base  (fluxo completo)
  1 - Só Criar      (apenas duplicar chamados, sem BC)
  2 - Só Base       (apenas adicionar BC em chamados ja criados)
"""
import csv
import io
import time

import pandas as pd

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QTextEdit, QComboBox,
    QPushButton, QGroupBox, QSizePolicy, QPlainTextEdit,
    QDialog, QStackedWidget, QMessageBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QTextCharFormat, QFont

from ui.tema_qt import (
    COR_SUCESSO, COR_ERRO, COR_STATUS, COR_INFO, FONTE_MONO,
)
from services.checkpoint import existe_pendente, foi_concluido, resumo as resumo_checkpoint
from services.flow_bc import _chave_checkpoint

MODO_COMPLETO = 0
MODO_SO_CRIAR = 1
MODO_SO_BC    = 2


# ---------------------------------------------------------------------------
# Dialog de Checkpoint
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
# Workers
# ---------------------------------------------------------------------------

class WorkerCompleto(QObject):
    log_signal = pyqtSignal(str, str)
    fim_signal = pyqtSignal(bool)

    def __init__(self, dados: dict, iniciar_do_zero: bool):
        super().__init__()
        self.dados = dados
        self.iniciar_do_zero = iniciar_do_zero

    def run(self):
        try:
            from services.automatic import Automatic

            def log(msg, tipo="info"):
                self.log_signal.emit(msg, tipo)

            resultado = Automatic(log).executar_fluxo(
                self.dados, iniciar_do_zero=self.iniciar_do_zero
            )
            self.fim_signal.emit(resultado)
        except Exception as e:
            self.log_signal.emit(f"Excecao inesperada: {e}", "error")
            self.fim_signal.emit(False)


class WorkerSoCriar(QObject):
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

            def log(msg, tipo="info"):
                self.log_signal.emit(msg, tipo)

            driver = _get_driver_manager(log).iniciar_driver_e_navegar()
            execute_3n_flow(
                driver          = driver,
                df              = self.dados["df"],
                descricao_base  = self.dados["descricao_base"],
                numero_chamado  = self.dados["numero_chamado"],
                usuario         = self.dados["usuario"],
                senha           = self.dados["senha"],
                log             = log,
                iniciar_do_zero = self.iniciar_do_zero,
            )
            self.fim_signal.emit(True)
        except Exception as e:
            self.log_signal.emit(f"Excecao inesperada: {e}", "error")
            self.fim_signal.emit(False)


class WorkerSoBC(QObject):
    log_signal = pyqtSignal(str, str)
    fim_signal = pyqtSignal(bool)

    def __init__(self, dados: dict, iniciar_do_zero: bool):
        super().__init__()
        self.dados = dados
        self.iniciar_do_zero = iniciar_do_zero

    def run(self):
        try:
            from services.automatic import _get_driver_manager
            from services.flow_bc import execute_bc_flow
            from services.kb_manager import executar_kb_unica

            def log(msg, tipo="info"):
                self.log_signal.emit(msg, tipo)

            driver      = _get_driver_manager(log).iniciar_driver_e_navegar()
            kb_function = lambda d, l: executar_kb_unica(d, l, self.dados["kb_config"])

            execute_bc_flow(
                driver          = driver,
                filhos          = self.dados["filhos"],
                usuario         = self.dados["usuario"],
                senha           = self.dados["senha"],
                log             = log,
                kb_function     = kb_function,
                iniciar_do_zero = self.iniciar_do_zero,
            )
            self.fim_signal.emit(True)
        except Exception as e:
            self.log_signal.emit(f"Excecao inesperada: {e}", "error")
            self.fim_signal.emit(False)


# ---------------------------------------------------------------------------
# Aba de Execucao
# ---------------------------------------------------------------------------

class AbaExecucao(QWidget):

    def __init__(self, kb_entries: list, parent=None):
        super().__init__(parent)
        self.kb_entries      = kb_entries
        self.linhas_csv      : list[list[str]] = []
        self.colunas_csv     : list[str]       = []
        self.linhas_csv_criar: list[list[str]] = []
        self.colunas_csv_criar: list[str]      = []
        self._filhos_bc      : list[str]       = []
        self._thread = None
        self._worker = None
        self._setup_ui()

    def atualizar_kbs(self, entries: list):
        self.kb_entries = entries
        for combo in [self.combo_kb_completo, self.combo_kb_so_bc]:
            combo.clear()
            for e in entries:
                combo.addItem(e["nome_artigo"])

    # ------------------------------------------------------------------
    # Setup UI
    # ------------------------------------------------------------------

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Seletor de modo
        modo_row = QHBoxLayout()
        modo_row.setSpacing(10)
        lbl_modo = QLabel("Modo:")
        lbl_modo.setStyleSheet("font-weight: bold;")
        modo_row.addWidget(lbl_modo)
        self.combo_modo = QComboBox()
        self.combo_modo.setFixedWidth(200)
        self.combo_modo.addItem("🔗  Criar + Base", MODO_COMPLETO)
        self.combo_modo.addItem("📋  Só Criar",      MODO_SO_CRIAR)
        self.combo_modo.addItem("📎  Só Base",       MODO_SO_BC)
        self.combo_modo.currentIndexChanged.connect(self._trocar_modo)
        modo_row.addWidget(self.combo_modo)
        modo_row.addStretch()
        layout.addLayout(modo_row)

        # Stack de paineis
        self.stack = QStackedWidget()
        self.stack.addWidget(self._criar_painel_completo())
        self.stack.addWidget(self._criar_painel_so_criar())
        self.stack.addWidget(self._criar_painel_so_bc())
        layout.addWidget(self.stack, 1)

        # Logs
        grp_logs = QGroupBox("Registro de Execução")
        logs_layout = QVBoxLayout(grp_logs)
        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setFont(QFont(FONTE_MONO, 11))
        self.txt_logs.setMinimumHeight(200)
        logs_layout.addWidget(self.txt_logs)
        layout.addWidget(grp_logs, 1)

    def _trocar_modo(self, index: int):
        self.stack.setCurrentIndex(index)
        self._limpar_logs()

    # ------------------------------------------------------------------
    # Helpers de construcao de UI
    # ------------------------------------------------------------------

    def _campo_credenciais(self) -> tuple:
        cred_row = QHBoxLayout()
        cred_row.setSpacing(12)

        mat_col = QVBoxLayout()
        mat_col.setSpacing(4)
        mat_col.addWidget(QLabel("Matrícula"))
        input_usuario = QLineEdit()
        input_usuario.setPlaceholderText("Matrícula")
        mat_col.addWidget(input_usuario)
        cred_row.addLayout(mat_col)

        senha_col = QVBoxLayout()
        senha_col.setSpacing(4)
        senha_col.addWidget(QLabel("Senha"))
        input_senha = QLineEdit()
        input_senha.setEchoMode(QLineEdit.EchoMode.Password)
        input_senha.setPlaceholderText("Lanlink@")
        senha_col.addWidget(input_senha)
        cred_row.addLayout(senha_col)

        return cred_row, input_usuario, input_senha

    def _campo_csv(self) -> tuple:
        col = QVBoxLayout()
        col.setSpacing(6)
        col.addWidget(QLabel("Dados de Iteração"))
        txt = QPlainTextEdit()
        txt.setPlaceholderText(
            "Marca/Modelo,Tombo\n"
            "POSITIVO C6200,212150/323265\n"
            "HP ProBook 450,198342/411280"
        )
        txt.setFont(QFont(FONTE_MONO, 11))
        col.addWidget(txt, 1)

        btn_row = QHBoxLayout()
        btn = QPushButton("Importar dados")
        btn.setObjectName("btn_secundario")
        lbl = QLabel("")
        lbl.setStyleSheet(f"color: {COR_SUCESSO};")
        btn_row.addWidget(btn)
        btn_row.addWidget(lbl)
        btn_row.addStretch()
        col.addLayout(btn_row)

        return col, txt, lbl, btn

    def _botoes_acao(self) -> tuple:
        row = QHBoxLayout()
        btn_iniciar = QPushButton("▶  INICIAR")
        btn_iniciar.setObjectName("btn_iniciar")
        btn_iniciar.setFixedHeight(40)
        row.addWidget(btn_iniciar)
        btn_limpar = QPushButton("Limpar Logs")
        btn_limpar.setObjectName("btn_secundario")
        btn_limpar.clicked.connect(self._limpar_logs)
        row.addWidget(btn_limpar)
        row.addStretch()
        return row, btn_iniciar

    def _mostrar_ajuda_marcadores(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Como usar os marcadores")
        dlg.setMinimumWidth(460)
        dlg.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        layout = QVBoxLayout(dlg)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        lbl = QLabel(
            "<p>O campo <b>Descrição</b> aceita marcadores "
            "<b><font face='Courier New'>{{COLUNA}}</font></b> que são substituídos "
            "automaticamente pelos dados de cada linha do CSV.</p>"

            "<p><b>📋 Dados de Iteração — formato CSV</b><br>"
            "A primeira linha é o cabeçalho (nomes das colunas):</p>"
            "<p><font face='Courier New'>"
            "MARCA,TOMBO,SETOR<br>"
            "LENOVO,262471,TI<br>"
            "HP,198342,RH"
            "</font></p>"

            "<p><b>✏️ Descrição com marcadores</b></p>"
            "<p><font face='Courier New'>"
            "Solicito atualização do equipamento {{MARCA}},<br>"
            "tombo {{TOMBO}}, setor {{SETOR}}."
            "</font></p>"

            "<p><b>✅ Resultado gerado no chamado (1ª linha)</b></p>"
            "<p><font face='Courier New'>"
            "Solicito atualização do equipamento LENOVO,<br>"
            "tombo 262471, setor TI."
            "</font></p>"

            "<p><font color='#6B7280'>"
            "• Marcador sem coluna correspondente fica em branco.<br>"
            "• Coluna sem marcador é ignorada silenciosamente.<br>"
            "• Os nomes são sensíveis a maiúsculas e minúsculas."
            "</font></p>"
        )
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        btn_fechar = QPushButton("Fechar")
        btn_fechar.setObjectName("btn_secundario")
        btn_fechar.setFixedWidth(100)
        btn_fechar.clicked.connect(dlg.accept)
        layout.addWidget(btn_fechar, alignment=Qt.AlignmentFlag.AlignRight)

        dlg.exec()

    # ------------------------------------------------------------------
    # Painel Criar + Base
    # ------------------------------------------------------------------

    def _criar_painel_completo(self) -> QWidget:
        painel = QWidget()
        cols = QHBoxLayout(painel)
        cols.setContentsMargins(0, 4, 0, 0)
        cols.setSpacing(24)

        col_esq = QVBoxLayout()
        col_esq.setSpacing(6)

        topo_row = QHBoxLayout()
        topo_row.setSpacing(12)

        chamado_col = QVBoxLayout()
        chamado_col.setSpacing(4)
        chamado_col.addWidget(QLabel("Chamado PAI"))
        self.input_chamado = QLineEdit()
        self.input_chamado.setPlaceholderText("Ex: S2123456")
        chamado_col.addWidget(self.input_chamado)
        topo_row.addLayout(chamado_col)

        mat_col = QVBoxLayout()
        mat_col.setSpacing(4)
        mat_col.addWidget(QLabel("Matrícula"))
        self.input_usuario = QLineEdit()
        self.input_usuario.setPlaceholderText("Matrícula")
        mat_col.addWidget(self.input_usuario)
        topo_row.addLayout(mat_col)

        senha_col = QVBoxLayout()
        senha_col.setSpacing(4)
        senha_col.addWidget(QLabel("Senha"))
        self.input_senha = QLineEdit()
        self.input_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_senha.setPlaceholderText("Lanlink@")
        senha_col.addWidget(self.input_senha)
        topo_row.addLayout(senha_col)

        col_esq.addLayout(topo_row)

        desc_header = QHBoxLayout()
        desc_header.setSpacing(6)
        desc_header.addWidget(QLabel("Descrição"))
        btn_ajuda_desc = QPushButton("?")
        btn_ajuda_desc.setObjectName("btn_ajuda")
        btn_ajuda_desc.setFixedSize(20, 20)
        btn_ajuda_desc.setToolTip("Como usar marcadores")
        btn_ajuda_desc.clicked.connect(self._mostrar_ajuda_marcadores)
        desc_header.addWidget(btn_ajuda_desc)
        desc_header.addStretch()
        col_esq.addLayout(desc_header)
        self.input_descricao = QPlainTextEdit()
        self.input_descricao.setPlainText("Solicito atualização de sistema...")
        self.input_descricao.setFont(QFont(FONTE_MONO, 11))
        col_esq.addWidget(self.input_descricao, 1)

        col_esq.addWidget(QLabel("Base de Conhecimento"))
        self.combo_kb_completo = QComboBox()
        self.combo_kb_completo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for e in self.kb_entries:
            self.combo_kb_completo.addItem(e["nome_artigo"])
        col_esq.addWidget(self.combo_kb_completo)

        btn_row, self.btn_iniciar_completo = self._botoes_acao()
        self.btn_iniciar_completo.clicked.connect(self._iniciar)
        col_esq.addLayout(btn_row)
        col_esq.addStretch()

        col_dir, self.txt_csv, self.lbl_csv_status, btn_imp = self._campo_csv()
        btn_imp.clicked.connect(self._importar_csv)

        cols.addLayout(col_esq, 1)
        cols.addLayout(col_dir, 1)
        return painel

    # ------------------------------------------------------------------
    # Painel So Criar
    # ------------------------------------------------------------------

    def _criar_painel_so_criar(self) -> QWidget:
        painel = QWidget()
        cols = QHBoxLayout(painel)
        cols.setContentsMargins(0, 4, 0, 0)
        cols.setSpacing(24)

        col_esq = QVBoxLayout()
        col_esq.setSpacing(6)

        topo_row = QHBoxLayout()
        topo_row.setSpacing(12)

        chamado_col = QVBoxLayout()
        chamado_col.setSpacing(4)
        chamado_col.addWidget(QLabel("Chamado PAI"))
        self.input_chamado_criar = QLineEdit()
        self.input_chamado_criar.setPlaceholderText("Ex: S2123456")
        chamado_col.addWidget(self.input_chamado_criar)
        topo_row.addLayout(chamado_col)

        mat_col = QVBoxLayout()
        mat_col.setSpacing(4)
        mat_col.addWidget(QLabel("Matrícula"))
        self.input_usuario_criar = QLineEdit()
        self.input_usuario_criar.setPlaceholderText("Matrícula")
        mat_col.addWidget(self.input_usuario_criar)
        topo_row.addLayout(mat_col)

        senha_col = QVBoxLayout()
        senha_col.setSpacing(4)
        senha_col.addWidget(QLabel("Senha"))
        self.input_senha_criar = QLineEdit()
        self.input_senha_criar.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_senha_criar.setPlaceholderText("Lanlink@")
        senha_col.addWidget(self.input_senha_criar)
        topo_row.addLayout(senha_col)

        col_esq.addLayout(topo_row)

        desc_header = QHBoxLayout()
        desc_header.setSpacing(6)
        desc_header.addWidget(QLabel("Descrição"))
        btn_ajuda_desc = QPushButton("?")
        btn_ajuda_desc.setObjectName("btn_ajuda")
        btn_ajuda_desc.setFixedSize(20, 20)
        btn_ajuda_desc.setToolTip("Como usar marcadores")
        btn_ajuda_desc.clicked.connect(self._mostrar_ajuda_marcadores)
        desc_header.addWidget(btn_ajuda_desc)
        desc_header.addStretch()
        col_esq.addLayout(desc_header)
        self.input_descricao_criar = QPlainTextEdit()
        self.input_descricao_criar.setPlainText("Solicito atualização de sistema...")
        self.input_descricao_criar.setFont(QFont(FONTE_MONO, 11))
        col_esq.addWidget(self.input_descricao_criar, 1)

        lbl_info = QLabel("ℹ️  Nenhuma Base de Conhecimento será aplicada.")
        lbl_info.setStyleSheet("color: #6B7280; font-size: 12px;")
        col_esq.addWidget(lbl_info)

        btn_row, self.btn_iniciar_criar = self._botoes_acao()
        self.btn_iniciar_criar.clicked.connect(self._iniciar)
        col_esq.addLayout(btn_row)
        col_esq.addStretch()

        col_dir, self.txt_csv_criar, self.lbl_csv_status_criar, btn_imp = self._campo_csv()
        btn_imp.clicked.connect(self._importar_csv_criar)

        cols.addLayout(col_esq, 1)
        cols.addLayout(col_dir, 1)
        return painel

    # ------------------------------------------------------------------
    # Painel So Base
    # ------------------------------------------------------------------

    def _criar_painel_so_bc(self) -> QWidget:
        painel = QWidget()
        cols = QHBoxLayout(painel)
        cols.setContentsMargins(0, 4, 0, 0)
        cols.setSpacing(24)

        col_esq = QVBoxLayout()
        col_esq.setSpacing(6)

        cred_row, self.input_usuario_bc, self.input_senha_bc = self._campo_credenciais()
        col_esq.addLayout(cred_row)

        col_esq.addWidget(QLabel("Base de Conhecimento"))
        self.combo_kb_so_bc = QComboBox()
        self.combo_kb_so_bc.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for e in self.kb_entries:
            self.combo_kb_so_bc.addItem(e["nome_artigo"])
        col_esq.addWidget(self.combo_kb_so_bc)

        btn_row, self.btn_iniciar_bc = self._botoes_acao()
        self.btn_iniciar_bc.clicked.connect(self._iniciar)
        col_esq.addLayout(btn_row)
        col_esq.addStretch()

        # Coluna direita — lista de filhos
        col_dir = QVBoxLayout()
        col_dir.setSpacing(6)
        col_dir.addWidget(QLabel("Chamados (um por linha)"))
        self.txt_filhos = QPlainTextEdit()
        self.txt_filhos.setPlaceholderText("S2198432\nS2198433\nS2198434")
        self.txt_filhos.setFont(QFont(FONTE_MONO, 11))
        col_dir.addWidget(self.txt_filhos, 1)

        btn_row_filhos = QHBoxLayout()
        btn_imp_filhos = QPushButton("Importar lista")
        btn_imp_filhos.setObjectName("btn_secundario")
        btn_imp_filhos.clicked.connect(self._importar_filhos)
        self.lbl_filhos_status = QLabel("")
        self.lbl_filhos_status.setStyleSheet(f"color: {COR_SUCESSO};")
        btn_row_filhos.addWidget(btn_imp_filhos)
        btn_row_filhos.addWidget(self.lbl_filhos_status)
        btn_row_filhos.addStretch()
        col_dir.addLayout(btn_row_filhos)

        cols.addLayout(col_esq, 1)
        cols.addLayout(col_dir, 1)
        return painel

    # ------------------------------------------------------------------
    # Importacao
    # ------------------------------------------------------------------

    def _importar_csv(self):
        self._processar_csv(self.txt_csv, self.lbl_csv_status, "completo")

    def _importar_csv_criar(self):
        self._processar_csv(self.txt_csv_criar, self.lbl_csv_status_criar, "criar")

    def _processar_csv(self, txt: QPlainTextEdit, lbl: QLabel, destino: str):
        texto = txt.toPlainText().strip()
        if not texto:
            lbl.setStyleSheet(f"color: {COR_ERRO};")
            lbl.setText("Cole o CSV antes de importar.")
            return
        try:
            rows = list(csv.reader(io.StringIO(texto)))
            if not rows:
                raise ValueError("Nenhuma linha encontrada.")
            colunas = [c.strip() for c in rows[0]]
            linhas  = [
                [v.strip() for v in row]
                for row in rows[1:]
                if any(v.strip() for v in row)
            ]
            if destino == "completo":
                self.colunas_csv  = colunas
                self.linhas_csv   = linhas
            else:
                self.colunas_csv_criar = colunas
                self.linhas_csv_criar  = linhas
            lbl.setStyleSheet(f"color: {COR_SUCESSO};")
            lbl.setText(f"✓ {len(linhas)} linha(s), {len(colunas)} coluna(s)")
        except Exception as e:
            lbl.setStyleSheet(f"color: {COR_ERRO};")
            lbl.setText(f"Erro: {e}")

    def _importar_filhos(self):
        texto = self.txt_filhos.toPlainText().strip()
        if not texto:
            self.lbl_filhos_status.setStyleSheet(f"color: {COR_ERRO};")
            self.lbl_filhos_status.setText("Cole os chamados antes de importar.")
            return
        filhos = [l.strip() for l in texto.splitlines() if l.strip()]
        if not filhos:
            self.lbl_filhos_status.setStyleSheet(f"color: {COR_ERRO};")
            self.lbl_filhos_status.setText("Nenhum chamado encontrado.")
            return
        self._filhos_bc = filhos
        self.lbl_filhos_status.setStyleSheet(f"color: {COR_SUCESSO};")
        self.lbl_filhos_status.setText(f"✓ {len(filhos)} chamado(s)")

    # ------------------------------------------------------------------
    # Iniciar
    # ------------------------------------------------------------------

    def _iniciar(self):
        modo = self.combo_modo.currentData()
        if modo == MODO_COMPLETO:
            self._iniciar_completo()
        elif modo == MODO_SO_CRIAR:
            self._iniciar_so_criar()
        else:
            self._iniciar_so_bc()

    def _iniciar_completo(self):
        erros = []
        if not self.linhas_csv:
            erros.append("Importe o CSV antes de iniciar.")
        if self.combo_kb_completo.currentIndex() < 0:
            erros.append("Selecione uma Base de Conhecimento.")
        if not self.input_chamado.text().strip():
            erros.append("Preencha o numero do Chamado PAI.")
        if not self.input_usuario.text().strip():
            erros.append("Preencha a matricula.")
        if not self.input_senha.text().strip():
            erros.append("Preencha a senha.")
        if erros:
            for e in erros: self._append_log(e, "error")
            return

        kb_entry = self._kb_entry(self.combo_kb_completo)
        if not kb_entry:
            return

        numero_chamado  = self.input_chamado.text().strip()
        iniciar_do_zero = self._verificar_checkpoint(numero_chamado)
        if iniciar_do_zero is None:
            return

        dados = {
            "descricao_base": self.input_descricao.toPlainText(),
            "kb_config":      {"keyword": kb_entry["keyword"], "nome_artigo": kb_entry["nome_artigo"]},
            "df":             pd.DataFrame(self.linhas_csv, columns=self.colunas_csv),
            "numero_chamado": numero_chamado,
            "usuario":        self.input_usuario.text().strip(),
            "senha":          self.input_senha.text().strip(),
        }
        self._set_em_execucao(True)
        self._iniciar_thread(WorkerCompleto(dados, iniciar_do_zero))

    def _iniciar_so_criar(self):
        erros = []
        if not self.linhas_csv_criar:
            erros.append("Importe o CSV antes de iniciar.")
        if not self.input_chamado_criar.text().strip():
            erros.append("Preencha o numero do Chamado PAI.")
        if not self.input_usuario_criar.text().strip():
            erros.append("Preencha a matricula.")
        if not self.input_senha_criar.text().strip():
            erros.append("Preencha a senha.")
        if erros:
            for e in erros: self._append_log(e, "error")
            return

        numero_chamado  = self.input_chamado_criar.text().strip()
        iniciar_do_zero = self._verificar_checkpoint(numero_chamado)
        if iniciar_do_zero is None:
            return

        dados = {
            "descricao_base": self.input_descricao_criar.toPlainText(),
            "df":             pd.DataFrame(self.linhas_csv_criar, columns=self.colunas_csv_criar),
            "numero_chamado": numero_chamado,
            "usuario":        self.input_usuario_criar.text().strip(),
            "senha":          self.input_senha_criar.text().strip(),
        }
        self._set_em_execucao(True)
        self._iniciar_thread(WorkerSoCriar(dados, iniciar_do_zero))

    def _iniciar_so_bc(self):
        erros = []
        if not self._filhos_bc:
            erros.append("Importe a lista de chamados antes de iniciar.")
        if self.combo_kb_so_bc.currentIndex() < 0:
            erros.append("Selecione uma Base de Conhecimento.")
        if not self.input_usuario_bc.text().strip():
            erros.append("Preencha a matricula.")
        if not self.input_senha_bc.text().strip():
            erros.append("Preencha a senha.")
        if erros:
            for e in erros: self._append_log(e, "error")
            return

        kb_entry = self._kb_entry(self.combo_kb_so_bc)
        if not kb_entry:
            return

        # Checkpoint indexado pelo primeiro filho
        chave           = _chave_checkpoint(self._filhos_bc)
        iniciar_do_zero = self._verificar_checkpoint(chave, label=self._filhos_bc[0])
        if iniciar_do_zero is None:
            return

        dados = {
            "filhos":     self._filhos_bc,
            "kb_config":  {"keyword": kb_entry["keyword"], "nome_artigo": kb_entry["nome_artigo"]},
            "usuario":    self.input_usuario_bc.text().strip(),
            "senha":      self.input_senha_bc.text().strip(),
        }
        self._set_em_execucao(True)
        self._iniciar_thread(WorkerSoBC(dados, iniciar_do_zero))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _kb_entry(self, combo: QComboBox) -> dict | None:
        nome  = combo.currentText()
        entry = next((e for e in self.kb_entries if e["nome_artigo"] == nome), None)
        if not entry:
            self._append_log("Base de Conhecimento nao encontrada.", "error")
        return entry

    def _verificar_checkpoint(self, chave: str, label: str = "") -> bool | None:
        if foi_concluido(chave):
            resp = QMessageBox.question(
                self,
                "Execução já concluída",
                f"O chamado <b>{label or chave}</b> já foi totalmente processado.\n\n"
                "Deseja executar novamente do zero?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if resp == QMessageBox.StandardButton.Yes:
                return True
            return None
        if not existe_pendente(chave):
            return False
        resumo = resumo_checkpoint(chave)
        dialog = CheckpointDialog(label or chave, resumo, parent=self)
        if not dialog.exec():
            return None
        return dialog.escolha == CheckpointDialog.DO_ZERO

    def _iniciar_thread(self, worker):
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait()
        self._worker = worker
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.log_signal.connect(self._append_log)
        self._worker.fim_signal.connect(self._fim_execucao)
        self._worker.fim_signal.connect(self._thread.quit)
        self._thread.start()

    def _fim_execucao(self, sucesso: bool):
        msg = "Fluxo concluido com sucesso." if sucesso else "Fluxo encerrado com falha. Verifique os logs."
        self._append_log(msg, "success" if sucesso else "error")
        self._set_em_execucao(False)

    def _set_em_execucao(self, em_exec: bool):
        label = "⏳ EM ANDAMENTO..." if em_exec else "▶  INICIAR"
        for btn in [self.btn_iniciar_completo, self.btn_iniciar_criar, self.btn_iniciar_bc]:
            btn.setEnabled(not em_exec)
            btn.setText(label)
        for w in [
            self.input_chamado,    self.input_usuario,    self.input_senha,
            self.combo_kb_completo, self.txt_csv,
            self.input_chamado_criar, self.input_usuario_criar, self.input_senha_criar,
            self.txt_csv_criar,
            self.input_usuario_bc, self.input_senha_bc,
            self.combo_kb_so_bc,   self.txt_filhos,
            self.combo_modo,
        ]:
            w.setEnabled(not em_exec)

    def _limpar_logs(self):
        self.txt_logs.clear()

    def _append_log(self, mensagem: str, tipo: str = "info"):
        ts     = time.strftime("%H:%M:%S")
        labels = {"info": "INFO", "status": "STATUS", "success": "SUCESSO", "error": "ERRO"}
        label  = labels.get(tipo, tipo.upper())
        linha  = f"[{ts}] [{label}] {mensagem}"
        cores  = {"success": COR_SUCESSO, "error": COR_ERRO, "status": COR_STATUS, "info": COR_INFO}
        cor    = cores.get(tipo, COR_INFO)
        fmt    = QTextCharFormat()
        fmt.setForeground(QColor(cor))
        cursor = self.txt_logs.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(linha + "\n", fmt)
        self.txt_logs.setTextCursor(cursor)
        self.txt_logs.ensureCursorVisible()