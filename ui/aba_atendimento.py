"""
ui/aba_atendimento.py — Aba "Iniciar Atendimento".

O tecnico agenda chamados (em Atendimento Programado) para serem iniciados numa
data/hora. Um QTimer verifica periodicamente e, quando bate a hora, dispara o
fluxo services.flow_atendimento.iniciar_atendimento no navegador.

Decisoes (memoria project_flow_atendimento): timer com o app aberto; fila de
varios chamados; descricao fixa.
"""
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QTextEdit,
    QPushButton, QGroupBox, QDateTimeEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QTimer, QDateTime
from PyQt6.QtGui import QColor, QTextCharFormat, QFont

from ui.tema_qt import (
    COR_SUCESSO, COR_ERRO, COR_STATUS, COR_INFO, COR_AVISO, FONTE_MONO,
)
from services.flow_atendimento import DESCRICAO_PADRAO


# ---------------------------------------------------------------------------
# Worker — processa um lote de chamados que ja venceram, numa unica sessao
# ---------------------------------------------------------------------------

class WorkerAtendimento(QObject):
    log_signal       = pyqtSignal(str, str)
    resultado_signal = pyqtSignal(dict)   # {"chamado": str, "sucesso": bool}
    fim_signal       = pyqtSignal(bool)

    def __init__(self, chamados: list, usuario: str, senha: str,
                 descricao: str, modo_teste: bool):
        super().__init__()
        self.chamados   = chamados
        self.usuario    = usuario
        self.senha      = senha
        self.descricao  = descricao
        self.modo_teste = modo_teste

    def run(self):
        try:
            from services.automatic import _get_driver_manager
            from services.flow_utils import _fazer_login
            from services.flow_atendimento import iniciar_atendimento

            def log(msg, tipo="info"):
                self.log_signal.emit(msg, tipo)

            driver = _get_driver_manager(log).iniciar_driver_e_navegar()

            if not _fazer_login(driver, self.usuario, self.senha, log):
                for c in self.chamados:
                    self.resultado_signal.emit({"chamado": c, "sucesso": False})
                self.fim_signal.emit(False)
                return

            houve_sucesso = False
            for chamado in self.chamados:
                log(f"Iniciando atendimento do chamado {chamado}...", "status")
                ok = iniciar_atendimento(
                    driver, log, chamado, self.descricao, self.modo_teste
                )
                self.resultado_signal.emit({"chamado": chamado, "sucesso": ok})
                houve_sucesso = houve_sucesso or ok

            self.fim_signal.emit(houve_sucesso)

        except Exception as e:
            self.log_signal.emit(f"Excecao inesperada: {e}", "error")
            self.fim_signal.emit(False)


# ---------------------------------------------------------------------------
# Aba Iniciar Atendimento
# ---------------------------------------------------------------------------

class AbaAtendimento(QWidget):

    COLUNAS = ["Chamado", "Agendado para", "Status"]

    STATUS_PENDENTE  = "PENDENTE"
    STATUS_EXECUTANDO = "EXECUTANDO"
    STATUS_CONCLUIDO = "CONCLUIDO"
    STATUS_ERRO      = "ERRO"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._agendados: list[dict] = []   # {chamado, quando(datetime), status}
        self._thread = None
        self._worker = None
        self._worker_ativo = False

        self._timer = QTimer(self)
        self._timer.setInterval(20_000)    # verifica a agenda a cada 20s
        self._timer.timeout.connect(self._verificar_agenda)

        self._setup_ui()

    # ------------------------------------------------------------------ UI
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        cols = QHBoxLayout()
        cols.setSpacing(24)

        # ── Coluna esquerda: credenciais + agendar ─────────────────────
        col_esq = QVBoxLayout()
        col_esq.setSpacing(6)

        cred_row = QHBoxLayout()
        cred_row.setSpacing(12)
        mat_col = QVBoxLayout()
        mat_col.addWidget(QLabel("Matrícula"))
        self.input_usuario = QLineEdit()
        self.input_usuario.setPlaceholderText("Matrícula")
        mat_col.addWidget(self.input_usuario)
        cred_row.addLayout(mat_col)
        senha_col = QVBoxLayout()
        senha_col.addWidget(QLabel("Senha"))
        self.input_senha = QLineEdit()
        self.input_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_senha.setPlaceholderText("Lanlink@")
        senha_col.addWidget(self.input_senha)
        cred_row.addLayout(senha_col)
        col_esq.addLayout(cred_row)

        col_esq.addWidget(QLabel("Chamado"))
        self.input_chamado = QLineEdit()
        self.input_chamado.setPlaceholderText("S2397518")
        col_esq.addWidget(self.input_chamado)

        col_esq.addWidget(QLabel("Iniciar em (dia e hora)"))
        self.input_quando = QDateTimeEdit()
        self.input_quando.setCalendarPopup(True)
        self.input_quando.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.input_quando.setDateTime(QDateTime.currentDateTime())
        col_esq.addWidget(self.input_quando)

        add_row = QHBoxLayout()
        self.btn_add = QPushButton("＋ Agendar")
        self.btn_add.setObjectName("btn_secundario")
        self.btn_add.clicked.connect(self._adicionar_agendamento)
        add_row.addWidget(self.btn_add)
        self.btn_remover = QPushButton("Remover selecionado")
        self.btn_remover.setObjectName("btn_secundario")
        self.btn_remover.clicked.connect(self._remover_selecionado)
        add_row.addWidget(self.btn_remover)
        add_row.addStretch()
        col_esq.addLayout(add_row)

        arm_row = QHBoxLayout()
        self.btn_ativar = QPushButton("▶  Ativar agendamento")
        self.btn_ativar.setObjectName("btn_iniciar")
        self.btn_ativar.setFixedHeight(40)
        self.btn_ativar.clicked.connect(self._toggle_agendamento)
        arm_row.addWidget(self.btn_ativar)
        btn_limpar = QPushButton("Limpar Logs")
        btn_limpar.setObjectName("btn_secundario")
        btn_limpar.clicked.connect(lambda: self.txt_logs.clear())
        arm_row.addWidget(btn_limpar)
        arm_row.addStretch()
        col_esq.addLayout(arm_row)
        col_esq.addStretch()

        # ── Coluna direita: tabela da agenda ───────────────────────────
        col_dir = QVBoxLayout()
        col_dir.setSpacing(6)
        col_dir.addWidget(QLabel("Agenda"))
        self.tabela = QTableWidget(0, len(self.COLUNAS))
        self.tabela.setHorizontalHeaderLabels(self.COLUNAS)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabela.setAlternatingRowColors(True)
        header = self.tabela.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tabela.setMinimumHeight(180)
        col_dir.addWidget(self.tabela)

        cols.addLayout(col_esq, 1)
        cols.addLayout(col_dir, 1)
        layout.addLayout(cols)

        # ── Logs ───────────────────────────────────────────────────────
        grp_logs = QGroupBox("Registro de Execução")
        logs_layout = QVBoxLayout(grp_logs)
        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setFont(QFont(FONTE_MONO, 11))
        self.txt_logs.setMinimumHeight(120)
        logs_layout.addWidget(self.txt_logs)
        layout.addWidget(grp_logs, 1)

    # ------------------------------------------------------ Agenda (dados)
    def _adicionar_agendamento(self):
        chamado = self.input_chamado.text().strip()
        if not chamado:
            self._append_log("Informe o número do chamado antes de agendar.", "error")
            return
        quando = self.input_quando.dateTime().toPyDateTime().replace(second=0, microsecond=0)
        self._agendados.append({
            "chamado": chamado,
            "quando":  quando,
            "status":  self.STATUS_PENDENTE,
        })
        self._append_log(
            f"Agendado: {chamado} para {quando.strftime('%d/%m/%Y %H:%M')}.", "info")
        self.input_chamado.clear()
        self._atualizar_tabela()

    def _remover_selecionado(self):
        linha = self.tabela.currentRow()
        if linha < 0 or linha >= len(self._agendados):
            return
        item = self._agendados[linha]
        if item["status"] == self.STATUS_EXECUTANDO:
            self._append_log("Não é possível remover um item em execução.", "error")
            return
        self._agendados.pop(linha)
        self._atualizar_tabela()

    def _atualizar_tabela(self):
        cores = {
            self.STATUS_PENDENTE:   COR_INFO,
            self.STATUS_EXECUTANDO: COR_STATUS,
            self.STATUS_CONCLUIDO:  COR_SUCESSO,
            self.STATUS_ERRO:       COR_ERRO,
        }
        self.tabela.setRowCount(0)
        for item in self._agendados:
            row = self.tabela.rowCount()
            self.tabela.insertRow(row)
            self.tabela.setItem(row, 0, QTableWidgetItem(item["chamado"]))
            self.tabela.setItem(row, 1, QTableWidgetItem(item["quando"].strftime("%d/%m/%Y %H:%M")))
            st_item = QTableWidgetItem(item["status"])
            st_item.setForeground(QColor(cores.get(item["status"], COR_INFO)))
            self.tabela.setItem(row, 2, st_item)

    # ------------------------------------------------------ Agendamento
    def _toggle_agendamento(self):
        if self._timer.isActive():
            self._timer.stop()
            self._set_armado(False)
            self._append_log("Agendamento pausado.", "status")
            return

        # Ativar: validar credenciais e ao menos um pendente
        erros = []
        if not self.input_usuario.text().strip():
            erros.append("Preencha a matrícula.")
        if not self.input_senha.text().strip():
            erros.append("Preencha a senha.")
        if not any(i["status"] == self.STATUS_PENDENTE for i in self._agendados):
            erros.append("Agende ao menos um chamado pendente.")
        if erros:
            for e in erros:
                self._append_log(e, "error")
            return

        self._set_armado(True)
        self._timer.start()
        self._append_log("Agendamento ativado. Verificando a cada 20s.", "success")
        self._verificar_agenda()   # checa imediatamente itens ja vencidos

    def _set_armado(self, armado: bool):
        self.btn_ativar.setText("⏸  Pausar agendamento" if armado else "▶  Ativar agendamento")
        self.input_usuario.setEnabled(not armado)
        self.input_senha.setEnabled(not armado)

    def _verificar_agenda(self):
        if self._worker_ativo:
            return
        agora = datetime.now()
        vencidos = [i for i in self._agendados
                    if i["status"] == self.STATUS_PENDENTE and i["quando"] <= agora]
        if not vencidos:
            return
        for i in vencidos:
            i["status"] = self.STATUS_EXECUTANDO
        self._atualizar_tabela()
        chamados = [i["chamado"] for i in vencidos]
        self._append_log(f"Hora de iniciar: {', '.join(chamados)}.", "status")
        self._iniciar_worker(chamados)

    def _iniciar_worker(self, chamados: list):
        self._worker_ativo = True
        self._worker = WorkerAtendimento(
            chamados=chamados,
            usuario=self.input_usuario.text().strip(),
            senha=self.input_senha.text().strip(),
            descricao=DESCRICAO_PADRAO,
            modo_teste=False,
        )
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.log_signal.connect(self._append_log)
        self._worker.resultado_signal.connect(self._aplicar_resultado)
        self._worker.fim_signal.connect(self._fim_worker)
        self._worker.fim_signal.connect(self._thread.quit)
        self._thread.start()

    def _aplicar_resultado(self, resultado: dict):
        chamado = resultado.get("chamado")
        sucesso = resultado.get("sucesso")
        for i in self._agendados:
            if i["chamado"] == chamado and i["status"] == self.STATUS_EXECUTANDO:
                i["status"] = self.STATUS_CONCLUIDO if sucesso else self.STATUS_ERRO
                break
        self._atualizar_tabela()

    def _fim_worker(self, _sucesso: bool):
        self._worker_ativo = False

    # ------------------------------------------------------------- Logs
    def _append_log(self, mensagem: str, tipo: str = "info"):
        import time
        ts     = time.strftime("%H:%M:%S")
        labels = {"info": "INFO", "status": "STATUS", "success": "SUCESSO", "error": "ERRO"}
        label  = labels.get(tipo, tipo.upper())
        linha  = f"[{ts}] [{label}] {mensagem}"
        cores  = {"success": COR_SUCESSO, "error": COR_ERRO, "status": COR_STATUS, "info": COR_AVISO}
        fmt    = QTextCharFormat()
        fmt.setForeground(QColor(cores.get(tipo, COR_INFO)))
        cursor = self.txt_logs.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(linha + "\n", fmt)
        self.txt_logs.setTextCursor(cursor)
        self.txt_logs.ensureCursorVisible()
