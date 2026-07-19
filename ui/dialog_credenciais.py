"""
ui/dialog_credenciais.py — Janela de cadastro das credenciais do CATI/Assyst.

Substitui os campos Matricula/Senha que antes eram repetidos em cada aba. A
senha vai para o Cofre do Windows (ver services/credenciais.py), nunca para o
disco.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QMessageBox,
)
from PyQt6.QtCore import Qt

from services import credenciais


class DialogCredenciais(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Credenciais")
        self.setFixedWidth(420)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        info = QLabel(
            "Credenciais do CATI/Assyst, usadas por todas as automações.<br>"
            "A senha é guardada no <b>Cofre de Credenciais do Windows</b>, "
            "não em arquivo."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addWidget(QLabel("Matrícula"))
        self.input_matricula = QLineEdit()
        self.input_matricula.setPlaceholderText("400123")
        layout.addWidget(self.input_matricula)

        layout.addWidget(QLabel("Senha"))
        self.input_senha = QLineEdit()
        self.input_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_senha.setPlaceholderText("Lanlink@")
        layout.addWidget(self.input_senha)

        self.chk_mostrar = QCheckBox("Mostrar senha")
        self.chk_mostrar.toggled.connect(self._alternar_senha)
        layout.addWidget(self.chk_mostrar)

        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_status)

        btns = QHBoxLayout()
        self.btn_salvar = QPushButton("Salvar")
        self.btn_apagar = QPushButton("Apagar")
        self.btn_fechar = QPushButton("Fechar")
        self.btn_salvar.clicked.connect(self._salvar)
        self.btn_apagar.clicked.connect(self._apagar)
        self.btn_fechar.clicked.connect(self.reject)
        btns.addWidget(self.btn_salvar)
        btns.addWidget(self.btn_apagar)
        btns.addWidget(self.btn_fechar)
        layout.addLayout(btns)

        self._carregar_existente()

    def _alternar_senha(self, mostrar: bool):
        modo = QLineEdit.EchoMode.Normal if mostrar else QLineEdit.EchoMode.Password
        self.input_senha.setEchoMode(modo)

    def _carregar_existente(self):
        matricula, senha = credenciais.carregar()
        if matricula:
            self.input_matricula.setText(matricula)
            self.input_senha.setText(senha)
            self.lbl_status.setText("✓ Credenciais salvas nesta máquina.")
        else:
            self.btn_apagar.setEnabled(False)
            self.lbl_status.setText("Nenhuma credencial salva ainda.")

    def _salvar(self):
        try:
            credenciais.salvar(
                self.input_matricula.text(),
                self.input_senha.text(),
            )
        except ValueError as e:
            QMessageBox.warning(self, "Credenciais", str(e))
            return
        except Exception as e:
            QMessageBox.critical(
                self, "Credenciais",
                f"Nao foi possivel gravar no Cofre do Windows:\n{e}",
            )
            return
        self.accept()

    def _apagar(self):
        resp = QMessageBox.question(
            self, "Credenciais",
            "Apagar a matrícula e remover a senha do Cofre do Windows?",
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        credenciais.apagar()
        self.input_matricula.clear()
        self.input_senha.clear()
        self.btn_apagar.setEnabled(False)
        self.lbl_status.setText("Credenciais apagadas.")


def obter_credenciais(parent=None) -> tuple[str, str] | None:
    """
    Devolve (matricula, senha) para os fluxos. Se nao houver nada salvo, abre o
    cadastro na hora em vez de so reclamar — o usuario resolve e segue sem
    perder o que ja preencheu na aba.

    Retorna None se ele desistir de cadastrar.
    """
    matricula, senha = credenciais.carregar()
    if matricula:
        return matricula, senha

    QMessageBox.information(
        parent, "Credenciais",
        "Nenhuma credencial cadastrada.\n\n"
        "Cadastre a matrícula e a senha para executar as automações. "
        "Depois, você pode alterá-las pelo menu ⓘ → Credenciais.",
    )
    if DialogCredenciais(parent).exec() != QDialog.DialogCode.Accepted:
        return None

    matricula, senha = credenciais.carregar()
    return (matricula, senha) if matricula else None
