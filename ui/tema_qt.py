"""
ui/tema.py — Estilos globais do PyQt6
"""

COR_FUNDO        = "#F5F7FA"
COR_PAINEL       = "#FFFFFF"
COR_BORDA        = "#D1D5DB"
COR_PRIMARIA     = "#2563EB"
COR_SUCESSO      = "#16A34A"
COR_ERRO         = "#DC2626"
COR_STATUS       = "#0891B2"
COR_INFO         = "#6B7280"
COR_AVISO        = "#D97706"
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
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {COR_PAINEL};
        color: {COR_TEXTO};
        border: 1px solid {COR_BORDA};
        selection-background-color: #DBEAFE;
        selection-color: #1E3A8A;
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
        color: white;
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
        border: 1px solid {COR_ERRO};
    }}
    QPushButton#btn_perigo:hover {{
        background-color: {COR_ERRO};
        color: white;
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
    QToolButton {{
        background-color: {COR_BTN_LIMPAR};
        color: {COR_TEXTO};
        border: 1px solid {COR_BORDA};
        border-radius: 5px;
        padding: 5px 12px;
        font-size: 13px;
        font-weight: bold;
    }}
    QToolButton:hover {{
        background-color: #D1D5DB;
    }}
    QToolButton::menu-indicator {{
        image: none;
    }}
    QMenu {{
        background-color: {COR_PAINEL};
        color: {COR_TEXTO};
        border: 1px solid {COR_BORDA};
        border-radius: 6px;
        padding: 4px;
    }}
    QMenu::item {{
        padding: 8px 20px;
        border-radius: 4px;
    }}
    QMenu::item:selected {{
        background-color: #DBEAFE;
        color: #1E3A8A;
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
    QScrollArea, QScrollBar {{
        background: transparent;
        border: none;
    }}
    QScrollBar:vertical {{
        background: {COR_FUNDO};
        width: 8px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: {COR_BORDA};
        border-radius: 4px;
    }}
    QGroupBox {{
        border: 1px solid {COR_BORDA};
        border-radius: 6px;
        margin-top: 12px;
        padding: 12px;
        font-weight: bold;
        background-color: {COR_PAINEL};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 6px;
        color: {COR_TEXTO_MUTED};
    }}
    QListWidget {{
        background-color: {COR_INPUT_BG};
        border: 1px solid {COR_BORDA};
        border-radius: 5px;
        padding: 4px;
        color: {COR_TEXTO};
    }}
    QListWidget::item {{
        padding: 8px;
        border-radius: 4px;
        color: {COR_TEXTO};
    }}
    QListWidget::item:selected {{
        background-color: #DBEAFE;
        color: #1E3A8A;
    }}
    QListWidget::item:hover {{
        background-color: #F3F4F6;
    }}
    QStatusBar {{
        background-color: {COR_FUNDO};
        color: {COR_TEXTO_MUTED};
        border-top: 1px solid {COR_BORDA};
    }}
    QSplitter::handle {{
        background: {COR_BORDA};
    }}
"""
