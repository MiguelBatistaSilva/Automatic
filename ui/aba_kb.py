"""
ui/aba_kb.py — Aba de gerenciamento das Bases de Conhecimento
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton,
    QGroupBox, QListWidget, QListWidgetItem,
    QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal

from ui.tema_qt import COR_ERRO, COR_SUCESSO, COR_TEXTO_MUTED


class AbaKB(QWidget):
    kbs_atualizadas = pyqtSignal(list)

    def __init__(self, kb_store, parent=None):
        super().__init__(parent)
        self.kb_store = kb_store
        self.entries = kb_store.carregar()
        self._setup_ui()
        self._carregar_lista()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # --- Lista de KBs ---
        grp_lista = QGroupBox("Bases Cadastradas")
        lista_layout = QVBoxLayout(grp_lista)

        self.lista = QListWidget()
        self.lista.setMinimumHeight(200)
        lista_layout.addWidget(self.lista)

        btn_remover = QPushButton("Remover Selecionada")
        btn_remover.setObjectName("btn_perigo")
        btn_remover.clicked.connect(self._remover)
        lista_layout.addWidget(btn_remover)

        layout.addWidget(grp_lista)

        # --- Adicionar nova KB ---
        grp_add = QGroupBox("Adicionar Nova Base")
        add_layout = QVBoxLayout(grp_add)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Palavra-chave:"))
        self.input_keyword = QLineEdit()
        self.input_keyword.setPlaceholderText("Ex: kaspersky")
        row1.addWidget(self.input_keyword)
        add_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Titulo do Artigo:"))
        self.input_artigo = QLineEdit()
        self.input_artigo.setPlaceholderText("Ex: BC - Instalacao e Atualizacao do Kaspersky")
        row2.addWidget(self.input_artigo)
        add_layout.addLayout(row2)

        self.lbl_status = QLabel("")
        add_layout.addWidget(self.lbl_status)

        btn_add = QPushButton("+ Adicionar Base")
        btn_add.setObjectName("btn_sucesso")
        btn_add.clicked.connect(self._adicionar)
        add_layout.addWidget(btn_add)

        layout.addWidget(grp_add)
        layout.addStretch()

    def _carregar_lista(self):
        self.lista.clear()
        for e in self.entries:
            item = QListWidgetItem(f"{e['nome_artigo']}  [{e['keyword']}]")
            item.setData(Qt.ItemDataRole.UserRole, e["nome_artigo"])
            self.lista.addItem(item)

    def _adicionar(self):
        keyword = self.input_keyword.text().strip()
        artigo  = self.input_artigo.text().strip()

        if not keyword or not artigo:
            self.lbl_status.setStyleSheet(f"color: {COR_ERRO};")
            self.lbl_status.setText("Preencha todos os campos.")
            return

        if any(e["nome_artigo"] == artigo for e in self.entries):
            self.lbl_status.setStyleSheet(f"color: {COR_ERRO};")
            self.lbl_status.setText("Artigo ja cadastrado.")
            return

        self.entries.append({"keyword": keyword, "nome_artigo": artigo})
        self.kb_store.salvar(self.entries)
        self._carregar_lista()
        self.kbs_atualizadas.emit(self.entries)

        self.input_keyword.clear()
        self.input_artigo.clear()
        self.lbl_status.setStyleSheet(f"color: {COR_SUCESSO};")
        self.lbl_status.setText("Base adicionada com sucesso!")

    def _remover(self):
        item = self.lista.currentItem()
        if not item:
            return
        nome = item.data(Qt.ItemDataRole.UserRole)
        resp = QMessageBox.question(
            self, "Confirmar",
            f"Remover '{nome}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if resp == QMessageBox.StandardButton.Yes:
            self.entries = [e for e in self.entries if e["nome_artigo"] != nome]
            self.kb_store.salvar(self.entries)
            self._carregar_lista()
            self.kbs_atualizadas.emit(self.entries)
