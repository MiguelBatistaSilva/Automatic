"""
ui/tema_qt.py — Estilos globais do PyQt6 (Light Mode)
"""

COR_FUNDO        = "#F0F2F5"
COR_PAINEL       = "#FFFFFF"
COR_BORDA        = "#D1D5DB"
COR_PRIMARIA     = "#2563EB"
COR_SUCESSO      = "#16A34A"
COR_ERRO         = "#DC2626"
COR_STATUS       = "#1D4ED8"
COR_INFO         = "#6B7280"
COR_TEXTO        = "#111827"
COR_TEXTO_MUTED  = "#6B7280"
COR_INPUT_BG     = "#FFFFFF"
COR_BTN_INICIAR  = "#2563EB"
COR_BTN_LIMPAR   = "#E5E7EB"

FONTE_MONO = "Consolas"
FONTE_UI   = "Segoe UI"

ESTILO_GLOBAL = f"""
    QMainWindow, QWidget {{
        background-color: {COR_FUNDO};
        color: {COR_TEXTO};
        font-family: {FONTE_UI};
        font-size: 13px;
    }}
    QTabWidget::pane {{
        border: 1px solid {COR_BORDA};
        background: {COR_PAINEL};
        border-radius: 6px;
    }}
    QTabBar::tab {{
        background: {COR_FUNDO};
        color: {COR_TEXTO_MUTED};
        padding: 8px 20px;
        border: 1px solid {COR_BORDA};
        border-bottom: none;
        border-radius: 4px 4px 0 0;
        margin-right: 2px;
    }}
    QTabBar::tab:selected {{
        background: {COR_PAINEL};
        color: {COR_TEXTO};
        font-weight: bold;
        border-bottom: 2px solid {COR_PRIMARIA};
    }}
    QLineEdit, QTextEdit, QPlainTextEdit {{
        background-color: {COR_INPUT_BG};
        color: {COR_TEXTO};
        border: 1px solid {COR_BORDA};
        border-radius: 5px;
        padding: 6px 10px;
        font-size: 13px;
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border: 1px solid {COR_PRIMARIA};
    }}
    QComboBox {{
        background-color: {COR_INPUT_BG};
        color: {COR_TEXTO};
        border: 1px solid {COR_BORDA};
        border-radius: 5px;
        padding: 6px 10px;
        font-size: 13px;
    }}
    QComboBox:focus {{
        border: 1px solid {COR_PRIMARIA};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 6px solid {COR_TEXTO_MUTED};
        margin-right: 6px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {COR_PAINEL};
        color: {COR_TEXTO};
        border: 1px solid {COR_BORDA};
        selection-background-color: {COR_PRIMARIA};
        selection-color: white;
        outline: none;
    }}
    QPushButton {{
        border-radius: 5px;
        padding: 8px 18px;
        font-size: 13px;
        font-weight: bold;
    }}
    QPushButton#btn_iniciar {{
        background-color: {COR_BTN_INICIAR};
        color: white;
        border: none;
    }}
    QPushButton#btn_iniciar:hover {{
        background-color: #1D4ED8;
    }}
    QPushButton#btn_iniciar:disabled {{
        background-color: #93C5FD;
        color: #FFFFFF;
    }}
    QPushButton#btn_secundario {{
        background-color: {COR_BTN_LIMPAR};
        color: {COR_TEXTO};
        border: 1px solid {COR_BORDA};
    }}
    QPushButton#btn_secundario:hover {{
        background-color: #D1D5DB;
    }}
    QPushButton#btn_perigo {{
        background-color: transparent;
        color: {COR_ERRO};
        border: 1px solid {COR_BORDA};
    }}
    QPushButton#btn_perigo:hover {{
        background-color: #FFF0F0;
        border-color: {COR_ERRO};
    }}
    QPushButton#btn_sucesso {{
        background-color: transparent;
        color: {COR_SUCESSO};
        border: 1px solid {COR_SUCESSO};
    }}
    QPushButton#btn_sucesso:hover {{
        background-color: {COR_SUCESSO};
        color: white;
    }}
    QLabel {{
        color: {COR_TEXTO};
        font-size: 13px;
    }}
    QLabel#label_secao {{
        color: {COR_TEXTO_MUTED};
        font-size: 11px;
        font-weight: bold;
        text-transform: uppercase;
        letter-spacing: 1px;
    }}
    QScrollArea {{
        border: none;
        background: transparent;
    }}
    QScrollBar:vertical {{
        background: {COR_FUNDO};
        width: 8px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: {COR_BORDA};
        border-radius: 4px;
        min-height: 20px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: #9CA3AF;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QGroupBox {{
        border: 1px solid {COR_BORDA};
        border-radius: 6px;
        margin-top: 4px;
        padding: 22px 12px 12px 12px;
        font-weight: bold;
        background-color: {COR_PAINEL};
    }}
    QGroupBox::title {{
        subcontrol-origin: padding;
        subcontrol-position: top left;
        left: 10px;
        top: 5px;
        padding: 0 4px;
        color: {COR_TEXTO_MUTED};
        background-color: transparent;
    }}
    QListWidget {{
        background-color: {COR_INPUT_BG};
        border: 1px solid {COR_BORDA};
        border-radius: 5px;
        padding: 4px;
        outline: none;
    }}
    QListWidget::item {{
        padding: 8px;
        border-radius: 4px;
        color: {COR_TEXTO};
    }}
    QListWidget::item:selected {{
        background-color: {COR_PRIMARIA};
        color: white;
    }}
    QListWidget::item:hover {{
        background-color: #EFF6FF;
    }}
    QSplitter::handle {{
        background: {COR_BORDA};
    }}
    QStatusBar {{
        background-color: {COR_PAINEL};
        color: {COR_TEXTO_MUTED};
        border-top: 1px solid {COR_BORDA};
    }}
    QMessageBox {{
        background-color: {COR_PAINEL};
        color: {COR_TEXTO};
    }}
    QMessageBox QPushButton {{
        background-color: {COR_BTN_LIMPAR};
        color: {COR_TEXTO};
        border: 1px solid {COR_BORDA};
        min-width: 70px;
    }}
"""
