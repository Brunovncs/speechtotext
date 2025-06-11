# services/transcriber.py

import whisper
from PySide6.QtCore import QThread, Signal

# Carrega o modelo globalmente para evitar recarregamentos
MODEL = whisper.load_model("base")

def get_model():
    """Retorna a instância do modelo Whisper carregado."""
    return MODEL

class TranscriptionThread(QThread):
    """Thread para transcrição de áudio."""
    transcription_finished = Signal(str, str, bool)
    transcription_error = Signal(str)
    
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