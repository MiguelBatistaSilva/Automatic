import time

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QTextEdit, QPlainTextEdit,
    QPushButton, QGroupBox, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QTextCharFormat, QFont

from ui.tema_qt import (
    COR_SUCESSO, COR_ERRO, COR_STATUS, COR_INFO, COR_AVISO, FONTE_MONO,
)


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

class WorkerSLA(QObject):
    log_signal       = pyqtSignal(str, str)
    resultado_signal = pyqtSignal(dict)   # um por chamado, inclui "numero_chamado"
    fim_signal       = pyqtSignal(bool)

    def __init__(self, chamados: list, usuario: str, senha: str, fila: str):
        super().__init__()
        self.chamados = chamados
        self.usuario  = usuario
        self.senha    = senha
        self.fila     = fila

    def run(self):
        try:
            # Piloto da migracao para Playwright: o SLA roda em navegador
            # proprio, fora do driver singleton do Selenium usado pelos demais
            # fluxos. Para voltar atras, basta reapontar os dois imports abaixo
            # para services.flow_sla / services.flow_utils e retomar o
            # _get_driver_manager.
            from services.browser_pw import NavegadorPW
            from services.flow_sla_pw import extrair_historico_chamado
            from services.browser_pw import _fazer_login_pw
            from services.sla_engine import calcular_sla

            def log(msg, tipo="info"):
                self.log_signal.emit(msg, tipo)

            # O Playwright sync precisa nascer e morrer NESTA thread; o `with`
            # garante que o navegador feche mesmo se algo estourar no meio.
            with NavegadorPW(log) as page:
                # Login uma unica vez; os chamados sao processados na mesma sessao.
                if not _fazer_login_pw(page, self.usuario, self.senha, log):
                    self.fim_signal.emit(False)
                    return

                total          = len(self.chamados)
                houve_sucesso  = False
                for i, numero in enumerate(self.chamados, 1):
                    log(f"[{i}/{total}] Analisando {numero}...", "status")
                    historico = extrair_historico_chamado(page, numero, log)
                    if historico is None:
                        self.resultado_signal.emit({
                            "numero_chamado": numero,
                            "falha":          True,
                            "mensagem":       "Falha ao extrair historico",
                        })
                        continue

                    resultado = calcular_sla(historico, self.fila)
                    resultado["numero_chamado"] = numero
                    resultado["total_acoes"]    = len(historico)
                    self.resultado_signal.emit(resultado)
                    houve_sucesso = True

            self.fim_signal.emit(houve_sucesso)

        except Exception as e:
            self.log_signal.emit(f"Excecao inesperada: {e}", "error")
            self.fim_signal.emit(False)


# ---------------------------------------------------------------------------
# Aba Análise de SLA
# ---------------------------------------------------------------------------

class AbaSLA(QWidget):

    COLUNAS = ["Chamado", "Início", "Tempo de SLA", "Status", "Ações"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread   = None
        self._worker   = None
        self._chamados : list[str] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # ── Bloco superior: duas colunas (inputs | lista de chamados) ───────
        cols = QHBoxLayout()
        cols.setSpacing(24)

        # Coluna esquerda — credenciais, fila e botões
        col_esq = QVBoxLayout()
        col_esq.setSpacing(6)

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

        col_esq.addWidget(QLabel("Fila"))
        self.combo_fila = QComboBox()
        from services.sla_engine import FILAS, FILA_PADRAO
        self.combo_fila.addItems(list(FILAS.keys()))
        idx = self.combo_fila.findText(FILA_PADRAO)
        if idx >= 0:
            self.combo_fila.setCurrentIndex(idx)
        col_esq.addWidget(self.combo_fila)

        btn_row = QHBoxLayout()
        self.btn_analisar = QPushButton("▶  Analisar SLA")
        self.btn_analisar.setObjectName("btn_iniciar")
        self.btn_analisar.setFixedHeight(40)
        self.btn_analisar.clicked.connect(self._iniciar)
        btn_row.addWidget(self.btn_analisar)
        btn_limpar = QPushButton("Limpar Logs")
        btn_limpar.setObjectName("btn_secundario")
        btn_limpar.clicked.connect(self._limpar_logs)
        btn_row.addWidget(btn_limpar)
        btn_row.addStretch()
        col_esq.addLayout(btn_row)
        col_esq.addStretch()

        # Coluna direita — lista de chamados
        col_dir = QVBoxLayout()
        col_dir.setSpacing(6)
        col_dir.addWidget(QLabel("Chamados (um por linha)"))
        self.txt_chamados = QPlainTextEdit()
        self.txt_chamados.setPlaceholderText("S2123456\nS2123457\nS2123458")
        self.txt_chamados.setFont(QFont(FONTE_MONO, 11))
        self.txt_chamados.setMaximumHeight(120)
        col_dir.addWidget(self.txt_chamados)

        imp_row = QHBoxLayout()
        imp_row.setSpacing(8)
        self.btn_importar = QPushButton("Importar lista")
        self.btn_importar.setObjectName("btn_secundario")
        self.btn_importar.clicked.connect(self._importar_chamados)
        imp_row.addWidget(self.btn_importar)
        self.lbl_chamados_status = QLabel("")
        self.lbl_chamados_status.setStyleSheet(f"color: {COR_SUCESSO};")
        imp_row.addWidget(self.lbl_chamados_status)
        imp_row.addStretch()
        col_dir.addLayout(imp_row)
        col_dir.addStretch()

        cols.addLayout(col_esq, 1)
        cols.addLayout(col_dir, 1)
        layout.addLayout(cols)

        # ── Tabela de resultados ───────────────────────────────────────────
        grp_resultados = QGroupBox("Resultados")
        res_layout = QVBoxLayout(grp_resultados)
        self.tabela = QTableWidget(0, len(self.COLUNAS))
        self.tabela.setHorizontalHeaderLabels(self.COLUNAS)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        # Tabela e somente leitura: sem selecao, para nao escurecer a linha ao clicar.
        self.tabela.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.tabela.setAlternatingRowColors(True)
        # Remove o realce escuro que o estilo aplica ao passar o mouse na linha.
        self.tabela.setStyleSheet(
            "QTableView::item:hover { background: transparent; }"
        )
        header = self.tabela.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Chamado
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Ações
        self.tabela.setMinimumHeight(140)
        res_layout.addWidget(self.tabela)
        layout.addWidget(grp_resultados, 1)

        # ── Logs ───────────────────────────────────────────────────────────
        grp_logs = QGroupBox("Registro de Execução")
        logs_layout = QVBoxLayout(grp_logs)
        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setFont(QFont(FONTE_MONO, 11))
        self.txt_logs.setMinimumHeight(100)
        logs_layout.addWidget(self.txt_logs)
        layout.addWidget(grp_logs, 1)

    # ------------------------------------------------------------------
    # Tabela de resultados
    # ------------------------------------------------------------------

    def _celula(self, texto: str, cor: str = "", negrito: bool = False) -> QTableWidgetItem:
        item = QTableWidgetItem(texto)
        if cor:
            item.setForeground(QColor(cor))
        if negrito:
            fonte = item.font()
            fonte.setBold(True)
            item.setFont(fonte)
        return item

    def _limpar_resultados(self):
        self.tabela.setRowCount(0)

    def _adicionar_linha(self, resultado: dict):
        row = self.tabela.rowCount()
        self.tabela.insertRow(row)
        numero = resultado.get("numero_chamado", "--")

        if resultado.get("falha"):
            self.tabela.setItem(row, 0, self._celula(numero, negrito=True))
            self.tabela.setItem(row, 1, self._celula("--"))
            self.tabela.setItem(row, 2, self._celula("--"))
            self.tabela.setItem(row, 3, self._celula(
                "✗ " + resultado.get("mensagem", "Falha"), cor=COR_ERRO, negrito=True))
            self.tabela.setItem(row, 4, self._celula("--"))
            return

        estourado = resultado.get("estourado", False)
        cor_status = COR_ERRO if estourado else COR_SUCESSO
        self.tabela.setItem(row, 0, self._celula(numero, negrito=True))
        self.tabela.setItem(row, 1, self._celula(resultado.get("inicio", "--")))
        self.tabela.setItem(row, 2, self._celula(resultado.get("tempo_gasto_str", "--")))
        self.tabela.setItem(row, 3, self._celula(
            resultado.get("mensagem", "--"), cor=cor_status, negrito=True))
        self.tabela.setItem(row, 4, self._celula(str(resultado.get("total_acoes", "--"))))

    # ------------------------------------------------------------------
    # Importação
    # ------------------------------------------------------------------

    def _importar_chamados(self):
        texto = self.txt_chamados.toPlainText().strip()
        if not texto:
            self.lbl_chamados_status.setStyleSheet(f"color: {COR_ERRO};")
            self.lbl_chamados_status.setText("Cole os chamados antes de importar.")
            return
        chamados = [l.strip() for l in texto.splitlines() if l.strip()]
        if not chamados:
            self.lbl_chamados_status.setStyleSheet(f"color: {COR_ERRO};")
            self.lbl_chamados_status.setText("Nenhum chamado encontrado.")
            return
        self._chamados = chamados
        self.lbl_chamados_status.setStyleSheet(f"color: {COR_SUCESSO};")
        self.lbl_chamados_status.setText(f"✓ {len(chamados)} chamado(s)")

    # ------------------------------------------------------------------
    # Lógica de execução
    # ------------------------------------------------------------------

    def _iniciar(self):
        # Permite analisar sem clicar em "Importar": le direto do campo.
        if not self._chamados:
            self._importar_chamados()

        erros = []
        if not self._chamados:
            erros.append("Preencha ao menos um chamado.")
        if not self.input_usuario.text().strip():
            erros.append("Preencha a matricula.")
        if not self.input_senha.text().strip():
            erros.append("Preencha a senha.")
        if erros:
            for e in erros:
                self._append_log(e, "error")
            return

        self._limpar_resultados()
        self._set_em_execucao(True)
        self._append_log(f"Iniciando analise de {len(self._chamados)} chamado(s)...", "status")

        self._worker = WorkerSLA(
            chamados=list(self._chamados),
            usuario=self.input_usuario.text().strip(),
            senha=self.input_senha.text().strip(),
            fila=self.combo_fila.currentText(),
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
        self._adicionar_linha(resultado)

        numero = resultado.get("numero_chamado", "--")
        if resultado.get("falha"):
            self._append_log(f"{numero}: {resultado.get('mensagem', 'falha')}", "error")
            return

        estourado = resultado.get("estourado", False)
        mensagem  = resultado.get("mensagem", "--")
        # SLA estourado e um resultado valido (nao falha de execucao): loga como
        # info, sem o rotulo [ERRO]. O destaque visual fica na tabela (Status vermelho).
        self._append_log(
            f"{numero} | Fila: {resultado.get('fila', '--')} | "
            f"Inicio: {resultado.get('inicio', '--')} | "
            f"Tempo: {resultado.get('tempo_gasto_str', '--')} | {mensagem}",
            "info" if estourado else "success",
        )

    def _fim_execucao(self, sucesso: bool):
        if not sucesso:
            self._append_log("Analise encerrada sem resultados. Verifique os logs.", "error")
        else:
            self._append_log("Analise concluida.", "success")
        self._set_em_execucao(False)

    def _set_em_execucao(self, em_exec: bool):
        self.btn_analisar.setEnabled(not em_exec)
        self.btn_analisar.setText("⏳ Analisando..." if em_exec else "▶  Analisar SLA")
        self.input_usuario.setEnabled(not em_exec)
        self.input_senha.setEnabled(not em_exec)
        self.combo_fila.setEnabled(not em_exec)
        self.txt_chamados.setEnabled(not em_exec)
        self.btn_importar.setEnabled(not em_exec)

    def _limpar_logs(self):
        self.txt_logs.clear()

    def _append_log(self, mensagem: str, tipo: str = "info"):
        ts     = time.strftime("%H:%M:%S")
        labels = {"info": "INFO", "status": "STATUS", "success": "SUCESSO", "error": "ERRO"}
        label  = labels.get(tipo, tipo.upper())
        linha  = f"[{ts}] [{label}] {mensagem}"
        cores  = {"success": COR_SUCESSO, "error": COR_ERRO, "status": COR_STATUS, "info": COR_AVISO}
        cor    = cores.get(tipo, COR_INFO)
        fmt    = QTextCharFormat()
        fmt.setForeground(QColor(cor))
        cursor = self.txt_logs.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(linha + "\n", fmt)
        self.txt_logs.setTextCursor(cursor)
        self.txt_logs.ensureCursorVisible()
