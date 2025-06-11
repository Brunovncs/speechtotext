# ui/main_ui.py

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, 
    QComboBox, QLabel, QCheckBox
)
from .styles import SAVE_AUDIO_CHECKBOX_STYLE, BTN_SAVE_AUDIO_STYLE

def setup_ui(parent_widget):
    """Configura e adiciona todos os widgets à janela principal."""
    main_layout = QVBoxLayout()

    # Seletor de microfone
    mic_layout = QHBoxLayout()
    mic_label = QLabel("Microfone:")
    parent_widget.mic_combo = QComboBox()
    mic_layout.addWidget(mic_label)
    mic_layout.addWidget(parent_widget.mic_combo)
    main_layout.addLayout(mic_layout)

    # Opção de salvar áudio
    save_layout = QHBoxLayout()
    parent_widget.save_audio_checkbox = QCheckBox("Salvar áudio após gravação")
    parent_widget.save_audio_checkbox.setStyleSheet(SAVE_AUDIO_CHECKBOX_STYLE)
    parent_widget.save_audio_checkbox.setToolTip("Se marcado, será solicitado onde salvar o arquivo de áudio")
    save_layout.addWidget(parent_widget.save_audio_checkbox)
    save_layout.addStretch()
    main_layout.addLayout(save_layout)

    # Botões de controle
    btn_layout = QHBoxLayout()
    parent_widget.btn_record = QPushButton("Iniciar Gravação")
    parent_widget.btn_file = QPushButton("Selecionar Áudio")
    btn_layout.addWidget(parent_widget.btn_record)
    btn_layout.addWidget(parent_widget.btn_file)
    main_layout.addLayout(btn_layout)

    # Label de status
    parent_widget.status_label = QLabel("Pronto para gravar ou selecionar arquivo")
    parent_widget.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
    main_layout.addWidget(parent_widget.status_label)

    # Área de texto
    parent_widget.text_edit = QTextEdit()
    parent_widget.text_edit.setReadOnly(True)
    main_layout.addWidget(parent_widget.text_edit)

    # Layout inferior
    bottom_layout = QHBoxLayout()
    parent_widget.btn_save_audio = QPushButton("Salvar Áudio")
    parent_widget.btn_save_audio.setVisible(False)
    parent_widget.btn_save_audio.setStyleSheet(BTN_SAVE_AUDIO_STYLE)
    bottom_layout.addWidget(parent_widget.btn_save_audio)
    bottom_layout.addStretch()
    parent_widget.btn_copy = QPushButton("Copiar Texto")
    bottom_layout.addWidget(parent_widget.btn_copy)
    main_layout.addLayout(bottom_layout)
    
    parent_widget.setLayout(main_layout)