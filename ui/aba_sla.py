import time

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QTextEdit,
    QPushButton, QGroupBox, QFrame,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QTextCharFormat, QFont

from ui.tema_qt import (
    COR_SUCESSO, COR_ERRO, COR_STATUS, COR_INFO,
    COR_BORDA, FONTE_MONO,
)


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

class WorkerSLA(QObject):
    log_signal       = pyqtSignal(str, str)
    resultado_signal = pyqtSignal(dict)
    fim_signal       = pyqtSignal(bool)

    def __init__(self, numero_chamado: str, usuario: str, senha: str):
        super().__init__()
        self.numero_chamado = numero_chamado
        self.usuario        = usuario
        self.senha          = senha

    def run(self):
        try:
            from services.automatic import _get_driver_manager
            from services.flow_sla import extrair_historico
            from services.sla_engine import calcular_sla

            def log(msg, tipo="info"):
                self.log_signal.emit(msg, tipo)

            driver    = _get_driver_manager(log).iniciar_driver_e_navegar()
            historico = extrair_historico(driver, self.numero_chamado, self.usuario, self.senha, log)

            if historico is None:
                self.fim_signal.emit(False)
                return

            resultado = calcular_sla(historico)
            resultado["total_acoes"] = len(historico)
            self.resultado_signal.emit(resultado)
            self.fim_signal.emit(True)

        except Exception as e:
            self.log_signal.emit(f"Excecao inesperada: {e}", "error")
            self.fim_signal.emit(False)


# ---------------------------------------------------------------------------
# Aba Análise de SLA
# ---------------------------------------------------------------------------

class AbaSLA(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = None
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # ── Linha de inputs + botões ───────────────────────────────────────
        topo_row = QHBoxLayout()
        topo_row.setSpacing(12)

        ref_col = QVBoxLayout()
        ref_col.setSpacing(4)
        ref_col.addWidget(QLabel("Referência"))
        self.input_chamado = QLineEdit()
        self.input_chamado.setPlaceholderText("Ex: S2123456")
        ref_col.addWidget(self.input_chamado)
        topo_row.addLayout(ref_col)

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

        btn_col = QVBoxLayout()
        btn_col.setSpacing(4)
        btn_col.addWidget(QLabel(""))
        self.btn_analisar = QPushButton("▶  Analisar SLA")
        self.btn_analisar.setObjectName("btn_iniciar")
        self.btn_analisar.setFixedHeight(34)
        self.btn_analisar.clicked.connect(self._iniciar)
        btn_col.addWidget(self.btn_analisar)
        topo_row.addLayout(btn_col)

        btn_limpar_col = QVBoxLayout()
        btn_limpar_col.setSpacing(4)
        btn_limpar_col.addWidget(QLabel(""))
        btn_limpar = QPushButton("Limpar Logs")
        btn_limpar.setObjectName("btn_secundario")
        btn_limpar.setFixedHeight(34)
        btn_limpar.clicked.connect(self._limpar_logs)
        btn_limpar_col.addWidget(btn_limpar)
        topo_row.addLayout(btn_limpar_col)

        topo_row.addStretch()
        layout.addLayout(topo_row)

        # ── Cards de resultado ─────────────────────────────────────────────
        cards_row = QHBoxLayout()
        cards_row.setSpacing(0)

        self._card_inicio = self._criar_card("Início", "--")
        self._card_gasto  = self._criar_card("Tempo de SLA", "--")
        self._card_status = self._criar_card("Status", "Aguardando análise")
        self._card_acoes  = self._criar_card("Total de Ações", "--")

        cards_row.addWidget(self._card_inicio)
        cards_row.addWidget(self._criar_separador())
        cards_row.addWidget(self._card_gasto)
        cards_row.addWidget(self._criar_separador())
        cards_row.addWidget(self._card_status)
        cards_row.addWidget(self._criar_separador())
        cards_row.addWidget(self._card_acoes)
        cards_row.addStretch()
        layout.addLayout(cards_row)

        # ── Logs ───────────────────────────────────────────────────────────
        grp_logs = QGroupBox("Registro de Execução")
        logs_layout = QVBoxLayout(grp_logs)
        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setFont(QFont(FONTE_MONO, 11))
        self.txt_logs.setMinimumHeight(200)
        logs_layout.addWidget(self.txt_logs)
        layout.addWidget(grp_logs, 1)

    # ------------------------------------------------------------------
    # Helpers de UI
    # ------------------------------------------------------------------

    def _criar_card(self, titulo: str, valor: str) -> QWidget:
        container = QWidget()
        col = QVBoxLayout(container)
        col.setSpacing(4)
        col.setContentsMargins(12, 8, 12, 8)

        lbl_titulo = QLabel(titulo.upper())
        lbl_titulo.setStyleSheet(f"color: {COR_INFO}; font-size: 10px; font-weight: bold;")
        col.addWidget(lbl_titulo)

        lbl_valor = QLabel(valor)
        lbl_valor.setStyleSheet("font-size: 16px; font-weight: bold;")
        col.addWidget(lbl_valor)

        container._lbl_valor = lbl_valor
        return container

    def _criar_separador(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background-color: {COR_BORDA};")
        return sep

    def _atualizar_card(self, card: QWidget, valor: str, cor: str = ""):
        lbl = card._lbl_valor
        lbl.setText(valor)
        estilo = "font-size: 16px; font-weight: bold;"
        if cor:
            estilo += f" color: {cor};"
        lbl.setStyleSheet(estilo)

    # ------------------------------------------------------------------
    # Lógica de execução
    # ------------------------------------------------------------------

    def _iniciar(self):
        erros = []
        if not self.input_chamado.text().strip():
            erros.append("Preencha a referencia do chamado.")
        if not self.input_usuario.text().strip():
            erros.append("Preencha a matricula.")
        if not self.input_senha.text().strip():
            erros.append("Preencha a senha.")
        if erros:
            for e in erros:
                self._append_log(e, "error")
            return

        self._resetar_cards()
        self._set_em_execucao(True)

        self._worker = WorkerSLA(
            numero_chamado=self.input_chamado.text().strip(),
            usuario=self.input_usuario.text().strip(),
            senha=self.input_senha.text().strip(),
        )
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.log_signal.connect(self._append_log)
        self._worker.resultado_signal.connect(self._exibir_resultado)
        self._worker.fim_signal.connect(self._fim_execucao)
        self._worker.fim_signal.connect(self._thread.quit)
        self._thread.start()

    def _exibir_resultado(self, resultado: dict):
        self._atualizar_card(self._card_inicio, resultado.get("inicio", "--"))
        self._atualizar_card(self._card_gasto,  resultado.get("tempo_gasto_str", "--"))
        self._atualizar_card(self._card_acoes,  str(resultado.get("total_acoes", "--")))

        estourado = resultado.get("estourado", False)
        mensagem  = resultado.get("mensagem", "--")
        self._atualizar_card(self._card_status, mensagem, cor=COR_ERRO if estourado else COR_SUCESSO)

        self._append_log(f"Inicio: {resultado.get('inicio', '--')}", "info")
        self._append_log(f"Tempo de SLA: {resultado.get('tempo_gasto_str', '--')}", "info")
        self._append_log(f"Status: {mensagem}", "error" if estourado else "success")

    def _fim_execucao(self, sucesso: bool):
        if not sucesso:
            self._append_log("Analise encerrada com falha. Verifique os logs.", "error")
        self._set_em_execucao(False)

    def _set_em_execucao(self, em_exec: bool):
        self.btn_analisar.setEnabled(not em_exec)
        self.btn_analisar.setText("⏳ Analisando..." if em_exec else "▶  Analisar SLA")
        self.input_chamado.setEnabled(not em_exec)
        self.input_usuario.setEnabled(not em_exec)
        self.input_senha.setEnabled(not em_exec)

    def _resetar_cards(self):
        for card in (self._card_inicio, self._card_gasto, self._card_acoes):
            self._atualizar_card(card, "--")
        self._atualizar_card(self._card_status, "Analisando...", cor=COR_STATUS)

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
