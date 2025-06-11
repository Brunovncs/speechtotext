# ui/styles.py

MAIN_APP_STYLESHEET = """
    QWidget {
        background-color: #000000;
        color: white;
        font-family: 'Segoe UI'; 
        font-size: 14px;
    }
    QPushButton {
        background-color: #1f1f1f;
        color: white;
        border-radius: 10px;
        padding: 6px 12px;
    }
    QPushButton:hover {
        background-color: #2b2b2b;
    }
    QComboBox, QTextEdit, QLineEdit {
        background-color: #1f1f1f;
        color: white;
        border: 2px solid #3a3a3a;
        border-radius: 10px;
    }
    QLineEdit:focus {
        border: 2px solid #81c784;
        background-color: #333333;
    }
    QLabel {
        color: white;
    }
"""

SAVE_AUDIO_CHECKBOX_STYLE = """
    QCheckBox {
        color: white;
    }
    QCheckBox::indicator {
        width: 16px;
        height: 16px;
    }
    QCheckBox::indicator:unchecked {
        border: 2px solid #555;
        background-color: #1f1f1f;
    }
    QCheckBox::indicator:checked {
        border: 2px solid #1f1f1f;
        background-color: #27ae60;
    }
"""

BTN_SAVE_AUDIO_STYLE = """
    QPushButton {
        background-color: #27ae60;
        color: white;
        font-weight: bold;
        padding: 8px 16px;
        border: none;
        border-radius: 12px;
    }
    QPushButton:hover {
        background-color: #66bb6a;
    }
    QPushButton:pressed {
        background-color: #388e3c;
    }
"""

BTN_RECORD_ACTIVE_STYLE = "background-color: #ff4444; color: white; font-weight: bold;"
BTN_COPY_SUCCESS_STYLE = "background-color: #27ae60; color: white; font-weight: bold;"