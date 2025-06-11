# app_window.py

import os
import sys
import tempfile
import shutil
from datetime import datetime

import pyperclip
from PySide6.QtWidgets import QWidget, QFileDialog, QMessageBox
from PySide6.QtCore import QTimer

# Importações dos componentes locais
from .ui.main_ui import setup_ui
from .ui.styles import BTN_RECORD_ACTIVE_STYLE, BTN_COPY_SUCCESS_STYLE
from .services.device_manager import get_audio_devices
from .services.audio_recorder import RecordingThread
from .services.transcriber import TranscriptionThread, get_model

class TranscricaoApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Transcrição de Áudio")
        self.setMinimumSize(600, 400)
        
        # Estado da aplicação
        self.model = get_model()
        self.is_recording = False
        self.recording_thread = None
        self.transcription_thread = None
        self.current_audio_file = None
        self.devices = None # Armazena a lista completa de dispositivos

        # Configuração da UI
        setup_ui(self)
        self._populate_mics()
        self._connect_signals()

    def _connect_signals(self):
        """Conecta os sinais dos widgets aos slots (métodos)."""
        self.btn_record.clicked.connect(self._on_record_toggle)
        self.btn_file.clicked.connect(self._on_select_file)
        self.btn_copy.clicked.connect(self._copy_text)
        self.btn_save_audio.clicked.connect(self._save_current_audio)

        self.copy_timer = QTimer()
        self.copy_timer.setSingleShot(True)
        self.copy_timer.timeout.connect(self._reset_copy_button)

    def _populate_mics(self):
        """Preenche o ComboBox com os microfones encontrados."""
        input_devices, all_devices = get_audio_devices()
        self.devices = all_devices

        if not input_devices:
            self.mic_combo.addItem("Nenhum microfone encontrado", None)
            return
        
        for real_idx, dev in input_devices:
            device_info = f"{dev['name']} ({dev['max_input_channels']} ch, {int(dev['default_samplerate'])}Hz)"
            self.mic_combo.addItem(device_info, real_idx)
    

    # Os métodos de lógica (_on_record_toggle, _start_recording, etc.) permanecem aqui.
    # Seus corpos são praticamente os mesmos, mas agora eles são mais focados em
    # controlar o fluxo da aplicação.
    def _on_record_toggle(self):
        """Alterna entre iniciar e parar gravação"""
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()
    # ... (copie e cole todos os métodos de '_' da classe TranscricaoApp original aqui)
    # Exemplo de um método adaptado:
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
                self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            
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