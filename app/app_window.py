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

from .threads import ModelLoaderThread 

class Speech2TextApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Transcrição de Áudio")
        self.setMinimumSize(600, 400)
        
        # Estado da aplicação
        self.current_model = None # ALTERADO: O modelo começa como None
        self.model_loader_thread = None # NOVO: Referência para a thread de carregamento
        self.loaded_model_name = None
        self.is_recording = False
        self.recording_thread = None
        self.transcription_thread = None
        self.current_audio_file = None
        self.devices = None 

        # Configuração da UI
        setup_ui(self)
        self._populate_mics()
        self._populate_models() # NOVO: Preenche o ComboBox de modelos
        self._connect_signals()
        
        # NOVO: Inicia o carregamento do modelo padrão
        self._change_model() 

    def _connect_signals(self):
        """Conecta os sinais dos widgets aos slots (métodos)."""
        self.btn_record.clicked.connect(self._on_record_toggle)
        self.btn_file.clicked.connect(self._on_select_file)
        self.btn_copy.clicked.connect(self._copy_text)
        self.btn_save_audio.clicked.connect(self._save_current_audio)

        # NOVO: Conecta o combobox de modelo e a thread
        self.model_combo.currentIndexChanged.connect(self._change_model)

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
    
    def _populate_models(self):
        """Adiciona os modelos disponíveis ao ComboBox."""
        models = {
            "Rápido (small)": "small",
            "Equilibrado (medium)": "medium",
            "Alta Qualidade (large-v3)": "large-v3",
            "Muito Rápido (base)": "base",
            "Extremamente Rápido (tiny)": "tiny"
        }
        for display_name, internal_name in models.items():
            self.model_combo.addItem(display_name, internal_name)
        
        # Define o 'medium' como padrão
        self.model_combo.setCurrentText("Equilibrado (medium)")
    
    # NOVO: Orquestra a mudança e carregamento de um novo modelo
    # def _change_model(self):
    #     """Inicia o carregamento de um novo modelo em uma thread."""
    #     model_name = self.model_combo.currentData()
    #     if not model_name:
    #         return

    #     # Desabilita a UI para evitar ações durante o carregamento
    #     self.set_ui_enabled(False)
    #     self.status_label.setText(f"Carregando modelo '{model_name}'... Por favor, aguarde.")
    #     self.status_label.setStyleSheet("color: orange; font-weight: bold;")
        
    #     # Cria e inicia a thread
    #     self.model_loader_thread = ModelLoaderThread(model_name)
    #     self.model_loader_thread.model_loaded.connect(self._on_model_loaded)
    #     self.model_loader_thread.start()
    
    
    def _change_model(self):
        """
        Inicia o carregamento de um novo modelo, com um diálogo de confirmação 
        se o download for necessário.
        """
        model_name = self.model_combo.currentData()
        if not model_name:
            return

        # 1. Evita recarregar o mesmo modelo que já está ativo.
        if model_name == self.loaded_model_name:
            return

        # 2. Verifica se o modelo já existe no cache do Whisper.
        cache_path = os.path.join(os.path.expanduser("~"), ".cache", "whisper")
        expected_model_file = os.path.join(cache_path, f"{model_name}.pt")

        proceed = True # Flag para controlar se devemos prosseguir

        # 3. Se o arquivo do modelo não existir, exibe o diálogo de confirmação.
        if not os.path.exists(expected_model_file):
            model_info = {
                "large-v3": "aprox. 3.1 GB", "medium": "aprox. 1.5 GB",
                "small": "aprox. 488 MB", "base": "aprox. 148 MB",
                "tiny": "aprox. 78 MB"
            }
            info = model_info.get(model_name, "Tamanho desconhecido")

            reply = QMessageBox.question(
                self,
                "Confirmar Download do Modelo",
                f"O modelo '{model_name}' precisa ser baixado ({info}).\n"
                "Esta é uma operação única e pode demorar alguns minutos.\n\n"
                "Deseja continuar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.No:
                proceed = False
                # 4. Lógica para reverter a seleção no ComboBox.
                # Bloqueia sinais para evitar que essa mudança chame _change_model de novo.
                self.model_combo.blockSignals(True)
                # Procura o índice do modelo que estava carregado anteriormente.
                if self.loaded_model_name:
                    previous_index = self.model_combo.findData(self.loaded_model_name)
                    self.model_combo.setCurrentIndex(previous_index)
                self.model_combo.blockSignals(False)

        # 5. Se o modelo já existe ou o usuário confirmou o download, continua o processo.
        if proceed:
            self.set_ui_enabled(False)
            self.status_label.setText(f"Carregando modelo '{model_name}'... Por favor, aguarde.")
            self.status_label.setStyleSheet("color: orange; font-weight: bold;")

            self.model_loader_thread = ModelLoaderThread(model_name)
            self.model_loader_thread.model_loaded.connect(self._on_model_loaded)
            self.model_loader_thread.start()
            
    # NOVO: Chamado quando a thread de carregamento termina
    def _on_model_loaded(self, model):
        """Recebe o modelo carregado e atualiza a aplicação."""
        if model:
            self.current_model = model
            self.status_label.setText(f"Modelo '{self.model_combo.currentData()}' pronto!")
            self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        else:
            self.current_model = None
            self.status_label.setText("Falha ao carregar o modelo!")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            QMessageBox.critical(self, "Erro de Modelo", "Não foi possível carregar o modelo selecionado.")

        # Reabilita a UI
        self.set_ui_enabled(True)
    
    def set_ui_enabled(self, enabled):
        """Habilita ou desabilita os principais widgets de interação."""
        self.btn_record.setEnabled(enabled)
        self.btn_file.setEnabled(enabled)
        self.model_combo.setEnabled(enabled)
        # Se estiver desabilitando, o texto deve ser claro
        if not enabled:
             self.btn_record.setText("Carregando...")
        else:
             self.btn_record.setText("Iniciar Gravação")
    
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
        self.model_combo.setEnabled(False)
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
        self.model_combo.setEnabled(True)
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
        self.model_combo.setEnabled(True)
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
        # ALTERADO: Verifica se um modelo está carregado antes de transcrever
        if self.current_model is None:
            QMessageBox.critical(self, "Erro", "Nenhum modelo de IA carregado. Selecione um modelo e aguarde o carregamento.")
            self.status_label.setText("Erro: Modelo não carregado.")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            return

        self.status_label.setText("Transcrevendo...")
        self.status_label.setStyleSheet("color: orange; font-weight: bold;")
        self.text_edit.setPlainText("Transcrevendo... Aguarde...")
        
            # NOVO: Desabilita botões e mostra a barra de progresso
        self.btn_record.setEnabled(False)
        self.btn_file.setEnabled(False)
        self.progress_bar.setVisible(True)
        
        # ALTERADO: Passa o modelo carregado para a thread de transcrição
        self.transcription_thread = TranscriptionThread(self.current_model, path, keep_audio)
        self.transcription_thread.transcription_finished.connect(self._on_transcription_success)
        self.transcription_thread.transcription_error.connect(self._on_transcription_error)
        self.transcription_thread.start()

    def _on_transcription_success(self, text, file_path, keep_audio):
        """Chamado quando transcrição é bem-sucedida"""
        self.progress_bar.setVisible(False)
        self.btn_record.setEnabled(True)
        self.btn_file.setEnabled(True)
    
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
        self.progress_bar.setVisible(False)
        self.btn_record.setEnabled(True)
        self.btn_file.setEnabled(True)
        
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
        # AQUI VOCÊ TAMBÉM DEVE INTERROMPER A THREAD DE CARREGAMENTO DE MODELO
        if self.model_loader_thread and self.model_loader_thread.isRunning():
            self.model_loader_thread.quit()
            self.model_loader_thread.wait()

        if self.is_recording and self.recording_thread:
            self.recording_thread.stop_recording()
            self.recording_thread.wait(3000)
        
        if self.recording_thread and self.recording_thread.isRunning():
            self.recording_thread.quit()
            self.recording_thread.wait()
        
        if self.transcription_thread and self.transcription_thread.isRunning():
            self.transcription_thread.quit()
            self.transcription_thread.wait()
        
        self._cleanup_temp_file()
        
        event.accept()