import sys
import os
import tempfile
import time
import numpy as np
from datetime import datetime

import whisper
import sounddevice as sd
import soundfile as sf
import pyperclip
import qtawesome as qta
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QTextEdit, QComboBox, QLabel, QFileDialog,
    QMessageBox, QCheckBox, QFrame, QToolBar, QToolButton
)
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt, QTimer, Signal, QThread

class RecordingThread(QThread):
    """Thread para gravação de áudio"""
    recording_finished = Signal(str, bool)  # Sinal com caminho do arquivo e se deve manter
    recording_error = Signal(str)     # Sinal com mensagem de erro
    recording_update = Signal(int)    # Sinal para atualizar tempo decorrido
    
    def __init__(self, device_idx, output_path, devices, keep_audio=False):
        super().__init__()
        self.device_idx = device_idx
        self.output_path = output_path
        self.devices = devices
        self.should_stop = False
        self.keep_audio = keep_audio
        
    def stop_recording(self):
        """Para a gravação"""
        self.should_stop = True
        
    def run(self):
        try:
            print(f"Iniciando gravação no device {self.device_idx}")
            
            # Obtém informações do dispositivo
            device_info = self.devices[self.device_idx]
            samplerate = int(device_info['default_samplerate'])
            channels = 1
            
            print(f"Gravando: {samplerate}Hz, {channels} canal(is)")
            
            # Lista para armazenar chunks de áudio
            audio_chunks = []
            chunk_duration = 0.1  # 100ms por chunk
            chunk_samples = int(chunk_duration * samplerate)
            
            # Tenta diferentes formatos de dados até encontrar um compatível
            dtypes_to_try = ['float32', 'int16', 'int32', 'float64']
            stream = None
            
            for dtype in dtypes_to_try:
                try:
                    print(f"Tentando formato: {dtype}")
                    stream = sd.InputStream(
                        device=self.device_idx,
                        channels=channels,
                        samplerate=samplerate,
                        dtype=dtype
                    )
                    print(f"Formato {dtype} aceito!")
                    break
                except Exception as e:
                    print(f"Formato {dtype} falhou: {e}")
                    if stream:
                        stream.close()
                    stream = None
            
            if stream is None:
                raise Exception("Nenhum formato de áudio compatível encontrado para este dispositivo")
            
            with stream:
                elapsed_seconds = 0
                
                while not self.should_stop:
                    # Lê um chunk de áudio
                    audio_chunk, overflowed = stream.read(chunk_samples)
                    
                    if overflowed:
                        print("Buffer overflow detectado")
                    
                    # Converte para float64 para consistência no processamento
                    if audio_chunk.dtype != np.float64:
                        audio_chunk = audio_chunk.astype(np.float64)
                    
                    audio_chunks.append(audio_chunk.copy())
                    
                    # Atualiza tempo a cada segundo aproximadamente
                    elapsed_seconds += chunk_duration
                    if elapsed_seconds >= 1.0:
                        self.recording_update.emit(int(len(audio_chunks) * chunk_duration))
                        elapsed_seconds = 0
                    
                    # Pequena pausa para não sobrecarregar
                    time.sleep(0.01)
            
            print("Gravação interrompida, processando áudio...")
            
            # Concatena todos os chunks
            if audio_chunks:
                recording = np.concatenate(audio_chunks, axis=0)
                
                # Normaliza o áudio se necessário
                if recording.dtype != np.float64:
                    recording = recording.astype(np.float64)
                
                # Salva o arquivo
                sf.write(self.output_path, recording, samplerate)
                print(f"Arquivo salvo: {self.output_path}")
                
                # Emite sinal de sucesso
                self.recording_finished.emit(self.output_path, self.keep_audio)
            else:
                self.recording_error.emit("Nenhum áudio foi gravado")
            
        except Exception as e:
            print(f"Erro na gravação: {e}")
            self.recording_error.emit(str(e))

class TranscriptionThread(QThread):
    """Thread para transcrição de áudio"""
    transcription_finished = Signal(str, str, bool)  # Sinal com texto transcrito, caminho do arquivo, e se deve manter
    transcription_error = Signal(str)     # Sinal com mensagem de erro
    
    def __init__(self, model, file_path, keep_audio=False):
        super().__init__()
        self.model = model
        self.file_path = file_path
        self.keep_audio = keep_audio
        
    def run(self):
        try:
            print(f"Iniciando transcrição de: {self.file_path}")
            result = self.model.transcribe(self.file_path, language="pt")
            text = result.get("text", "").strip()
            print(f"Transcrição concluída: {len(text)} caracteres")
            
            self.transcription_finished.emit(text, self.file_path, self.keep_audio)
            
        except Exception as e:
            print(f"Erro na transcrição: {e}")
            self.transcription_error.emit(str(e))

class TranscricaoApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Transcrição de Áudio")
        self.setMinimumSize(600, 400)
        self.model = whisper.load_model("base")  # Carrega o modelo uma vez
        self.is_recording = False
        self.recording_thread = None
        self.transcription_thread = None
        self.current_audio_file = None  # Para controle de arquivos temporários

        # Layout principal
        main_layout = QVBoxLayout()

        # Seletor de microfone
        mic_layout = QHBoxLayout()
        mic_label = QLabel("Microfone:")
        self.mic_combo = QComboBox()
        self._populate_mics()
        mic_layout.addWidget(mic_label)
        mic_layout.addWidget(self.mic_combo)
        main_layout.addLayout(mic_layout)

        # Opção de salvar áudio
        save_layout = QHBoxLayout()
        self.save_audio_checkbox = QCheckBox("Salvar áudio após gravação")
        self.save_audio_checkbox.setStyleSheet("""
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
                background-color: #27ae60;  /* cor quando está marcado */
            }
        """)
        self.save_audio_checkbox.setToolTip("Se marcado, será solicitado onde salvar o arquivo de áudio")
        save_layout.addWidget(self.save_audio_checkbox)
        save_layout.addStretch()  # Empurra checkbox para a esquerda
        main_layout.addLayout(save_layout)

        # Botões de gravação e seleção de arquivo
        btn_layout = QHBoxLayout()
        self.btn_record = QPushButton("Iniciar Gravação")
        self.btn_record.clicked.connect(self._on_record_toggle)
        self.btn_file = QPushButton("Selecionar Áudio")
        self.btn_file.clicked.connect(self._on_select_file)
        btn_layout.addWidget(self.btn_record)
        btn_layout.addWidget(self.btn_file)
        main_layout.addLayout(btn_layout)

        # Label de status
        self.status_label = QLabel("Pronto para gravar ou selecionar arquivo")
        self.status_label.setStyleSheet("color: #2ecc71; font-weight: bold;")
        main_layout.addWidget(self.status_label)

        # Área de texto com transcrição
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        main_layout.addWidget(self.text_edit)

        # Layout inferior com botões
        bottom_layout = QHBoxLayout()
        
        # Botão de salvar áudio (inicialmente oculto)
        self.btn_save_audio = QPushButton("Salvar Áudio")
        self.btn_save_audio.clicked.connect(self._save_current_audio)
        self.btn_save_audio.setVisible(False)
        self.btn_save_audio.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
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
        """)
        bottom_layout.addWidget(self.btn_save_audio)
        
        bottom_layout.addStretch()  # Espaço flexível
        
        # Botão de copiar
        self.btn_copy = QPushButton("Copiar Texto")
        self.btn_copy.clicked.connect(self._copy_text)
        bottom_layout.addWidget(self.btn_copy)
        
        main_layout.addLayout(bottom_layout)

        # Timer para resetar o texto do botão copiar
        self.copy_timer = QTimer()
        self.copy_timer.setSingleShot(True)
        self.copy_timer.timeout.connect(self._reset_copy_button)

        self.setLayout(main_layout)
        
        # Estilo geral da interface
        self.setStyleSheet("""
            QWidget {
                background-color: #000000;
                color: white;
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
            QCheckBox {
                color: white;
            }
        """)

    def _populate_mics(self):
        try:
            self.devices = sd.query_devices()
            inputs = []
            
            print("Dispositivos de áudio disponíveis:")
            for idx, dev in enumerate(self.devices):
                if dev['max_input_channels'] > 0:
                    inputs.append((idx, dev))
                    print(f"  {idx}: {dev['name']} - {dev['max_input_channels']} canais - {dev['default_samplerate']}Hz")
            
            if not inputs:
                self.mic_combo.addItem("Nenhum microfone encontrado", None)
                return
            
            for real_idx, dev in inputs:
                device_info = f"{dev['name']} ({dev['max_input_channels']} ch, {int(dev['default_samplerate'])}Hz)"
                self.mic_combo.addItem(device_info, real_idx)
                
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao listar microfones: {e}")
            self.mic_combo.addItem("Erro ao carregar microfones", None)

    def _on_record_toggle(self):
        """Alterna entre iniciar e parar gravação"""
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        """Inicia a gravação"""
        device_idx = self.mic_combo.currentData()
        if device_idx is None:
            QMessageBox.warning(self, "Erro", "Selecione um microfone válido.")
            return

        # Verifica se deve salvar o áudio
        save_audio = self.save_audio_checkbox.isChecked()
        
        if save_audio:
            # Solicita onde salvar o arquivo
            output_path, _ = QFileDialog.getSaveFileName(
                self, "Salvar Gravação como WAV", "gravacao.wav", "WAV Files (*.wav)"
            )
            if not output_path:
                return
        else:
            # Usa arquivo temporário
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(tempfile.gettempdir(), f"transcricao_temp_{timestamp}.wav")

        self.current_audio_file = output_path
        self.is_recording = True
        self.btn_record.setText("Parar Gravação")
        self.btn_record.setStyleSheet("background-color: #ff4444; color: white; font-weight: bold;")
        self.btn_file.setEnabled(False)  # Desabilita seleção de arquivo durante gravação
        self.save_audio_checkbox.setEnabled(False)  # Desabilita checkbox durante gravação
        self.status_label.setText("Gravando: 0 segundos")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        
        # Oculta botão de salvar áudio se estiver visível
        self.btn_save_audio.setVisible(False)

        # Cria e configura thread de gravação
        self.recording_thread = RecordingThread(device_idx, output_path, self.devices, save_audio)
        self.recording_thread.recording_finished.connect(self._on_recording_success)
        self.recording_thread.recording_error.connect(self._on_recording_error)
        self.recording_thread.recording_update.connect(self._update_recording_time)
        self.recording_thread.start()

    def _stop_recording(self):
        """Para a gravação"""
        if self.recording_thread:
            self.recording_thread.stop_recording()
            self.status_label.setText("Finalizando gravação...")
            self.status_label.setStyleSheet("color: orange; font-weight: bold;")

    def _update_recording_time(self, seconds):
        """Atualiza tempo de gravação"""
        minutes = seconds // 60
        secs = seconds % 60
        if minutes > 0:
            self.status_label.setText(f"Gravando: {minutes}min {secs}s")
        else:
            self.status_label.setText(f"Gravando: {secs} segundos")

    def _on_recording_success(self, output_path, keep_audio):
        """Chamado quando gravação é bem-sucedida"""
        print("Gravação bem-sucedida, iniciando transcrição...")
        
        self.is_recording = False
        self.btn_record.setText("Iniciar Gravação")
        self.btn_record.setStyleSheet("")  # Remove estilo customizado
        self.btn_file.setEnabled(True)  # Reabilita seleção de arquivo
        self.save_audio_checkbox.setEnabled(True)  # Reabilita checkbox
        self.status_label.setText("Gravação concluída! Iniciando transcrição...")
        self.status_label.setStyleSheet("color: green; font-weight: bold;")
        
        # Inicia transcrição automaticamente
        self._transcribe_file(output_path, keep_audio)

    def _on_recording_error(self, error_msg):
        """Chamado quando há erro na gravação"""
        print(f"Erro na gravação: {error_msg}")
        
        self.is_recording = False
        self.btn_record.setText("Iniciar Gravação")
        self.btn_record.setStyleSheet("")  # Remove estilo customizado
        self.btn_file.setEnabled(True)  # Reabilita seleção de arquivo
        self.save_audio_checkbox.setEnabled(True)  # Reabilita checkbox
        self.status_label.setText("Erro na gravação")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        QMessageBox.critical(self, "Erro na Gravação", f"Falha ao gravar: {error_msg}")

    def _on_select_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir Arquivo de Áudio", ".", 
            "Áudio (*.wav *.m4a *.mp3 *.flac *.ogg)"
        )
        if path:
            self._transcribe_file(path, keep_audio=True)  # Arquivos selecionados são sempre mantidos

    def _transcribe_file(self, path, keep_audio=False):
        """Transcreve arquivo de áudio"""
        self.status_label.setText("Transcrevendo...")
        self.status_label.setStyleSheet("color: orange; font-weight: bold;")
        self.text_edit.setPlainText("Transcrevendo... Aguarde...")
        
        # Cria e configura thread de transcrição
        self.transcription_thread = TranscriptionThread(self.model, path, keep_audio)
        self.transcription_thread.transcription_finished.connect(self._on_transcription_success)
        self.transcription_thread.transcription_error.connect(self._on_transcription_error)
        self.transcription_thread.start()

    def _on_transcription_success(self, text, file_path, keep_audio):
        """Chamado quando transcrição é bem-sucedida"""
        if text:
            self.text_edit.setPlainText(text)
            self.status_label.setText("Transcrição concluída!")
            self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            
            # Se o áudio não deve ser mantido e é um arquivo temporário, mostra botão para salvar
            if not keep_audio and file_path == self.current_audio_file:
                self.btn_save_audio.setVisible(True)
                self.status_label.setText("Transcrição concluída! (arquivo temporário)")
            
        else:
            self.text_edit.setPlainText("Nenhum texto foi detectado no áudio.")
            self.status_label.setText("Nenhum texto detectado")
            self.status_label.setStyleSheet("color: orange; font-weight: bold;")
            
            # Remove arquivo temporário se não foi detectado texto
            if not keep_audio and file_path == self.current_audio_file:
                self._cleanup_temp_file()

        # Se não deve manter o áudio e não é o arquivo atual (foi um arquivo temporário antigo)
        if not keep_audio and file_path != self.current_audio_file:
            self._cleanup_file(file_path)

    def _on_transcription_error(self, error_msg):
        """Chamado quando há erro na transcrição"""
        self.status_label.setText("Erro na transcrição")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        self.text_edit.setPlainText(f"Erro na transcrição: {error_msg}")
        QMessageBox.critical(self, "Erro na Transcrição", f"Falha na transcrição: {error_msg}")

    def _save_current_audio(self):
        """Salva o arquivo de áudio atual"""
        if not self.current_audio_file or not os.path.exists(self.current_audio_file):
            QMessageBox.warning(self, "Erro", "Nenhum arquivo de áudio para salvar.")
            return
        
        # Solicita onde salvar
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Salvar Áudio", "gravacao.wav", "WAV Files (*.wav)"
        )
        
        if save_path:
            try:
                # Copia o arquivo temporário para o local escolhido
                import shutil
                shutil.copy2(self.current_audio_file, save_path)
                
                # Atualiza status
                self.status_label.setText(f"Áudio salvo! Transcrição concluída!")
                self.status_label.setStyleSheet("color: green; font-weight: bold;")
                
                # Oculta botão de salvar
                self.btn_save_audio.setVisible(False)
                
                QMessageBox.information(self, "Áudio Salvo", f"Arquivo salvo em:\n{save_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "Erro ao Salvar", f"Falha ao salvar áudio: {e}")

    def _copy_text(self):
        text = self.text_edit.toPlainText()
        if text and text != "Transcrevendo... Aguarde..." and not text.startswith("Erro na transcrição"):
            pyperclip.copy(text)
            
            # Muda o texto do botão para "Copiado!"
            self.btn_copy.setText("Copiado!")
            self.btn_copy.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
            self.btn_copy.setEnabled(False)  # Desabilita o botão temporariamente
            
            # Inicia o timer para resetar o botão após 2 segundos
            self.copy_timer.start(2000)
        else:
            QMessageBox.warning(self, "Vazio", "Não há texto para copiar.")

    def _reset_copy_button(self):
        """Reseta o texto e estilo do botão copiar"""
        self.btn_copy.setText("Copiar Texto")
        self.btn_copy.setStyleSheet("")  # Remove estilo customizado
        self.btn_copy.setEnabled(True)  # Reabilita o botão

    def _cleanup_temp_file(self):
        """Remove o arquivo temporário atual"""
        if self.current_audio_file and os.path.exists(self.current_audio_file):
            try:
                os.remove(self.current_audio_file)
                print(f"Arquivo temporário removido: {self.current_audio_file}")
            except Exception as e:
                print(f"Erro ao remover arquivo temporário: {e}")
            finally:
                self.current_audio_file = None

    def _cleanup_file(self, file_path):
        """Remove um arquivo específico"""
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"Arquivo removido: {file_path}")
            except Exception as e:
                print(f"Erro ao remover arquivo: {e}")

    def closeEvent(self, event):
        """Garantir que threads sejam finalizadas e arquivos temporários removidos ao fechar o app"""
        if self.is_recording and self.recording_thread:
            self.recording_thread.stop_recording()
            self.recording_thread.wait(3000)  # Aguarda até 3 segundos
        
        if self.recording_thread and self.recording_thread.isRunning():
            self.recording_thread.quit()
            self.recording_thread.wait()
        
        if self.transcription_thread and self.transcription_thread.isRunning():
            self.transcription_thread.quit()
            self.transcription_thread.wait()
        
        # Remove arquivo temporário se existir
        self._cleanup_temp_file()
        
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # palette escura
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor("#121212"))
    pal.setColor(QPalette.WindowText, QColor("#EEEEEE"))
    pal.setColor(QPalette.Base, QColor("#1E1E1E"))
    pal.setColor(QPalette.Button, QColor("#2C2C2C"))
    pal.setColor(QPalette.ButtonText, QColor("#EEEEEE"))
    app.setPalette(pal)
    # stylesheet
    app.setStyleSheet("""
    QWidget { font-family: 'Segoe UI'; font-size:14px; }
    QFrame#card {
      background:#1E1E1E; border-radius:10px;
      border:1px solid rgba(255,255,255,0.05); padding:8px;
    }
    QToolBar#toolbar { background:#1E1E1E; border-bottom:1px solid rgba(255,255,255,0.1); }
    QPushButton {
      background:#2C2C2C; color:#EEEEEE; border:none;
      border-radius:6px; padding:8px 16px;
    }
    QPushButton:hover { background:#3A3A3A; }
    QComboBox, QTextEdit {
      background:#1E1E1E; color:#EEEEEE;
      border:1px solid rgba(255,255,255,0.1); border-radius:6px;
    }
    QLabel { color:#CCCCCC; }
    QCheckBox { color:#EEEEEE; }
    QCheckBox::indicator {
      width:16px; height:16px; border:1px solid #555;
      border-radius:4px; background:#2C2C2C;
    }
    QCheckBox::indicator:checked {
      background:#2ecc71; border:1px solid #2196F3;
    }
    """)
    window = TranscricaoApp()
    window.show()
    sys.exit(app.exec())