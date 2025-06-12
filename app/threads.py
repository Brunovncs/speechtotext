import whisper
from PySide6.QtCore import QThread, Signal
import torch

class ModelLoaderThread(QThread):
    """
    Uma thread para carregar um modelo do Whisper em segundo plano,
    evitando que a interface do usuário congele.
    """
    # Sinal que será emitido quando o modelo estiver carregado.
    # Ele enviará o objeto do modelo como argumento.
    model_loaded = Signal(object)

    def __init__(self, model_name):
        super().__init__()
        self.model_name = model_name
        self.model = None
    
    def run(self):
        """
        Esta função é executada quando a thread inicia.
        O carregamento pesado acontece aqui.
        """
        try:
            # Verifica se há uma GPU CUDA disponível para melhor desempenho
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"Carregando modelo '{self.model_name}' no dispositivo: {device}...")
            
            self.model = whisper.load_model(self.model_name, device=device)
            self.model_loaded.emit(self.model)
            
        except Exception as e:
            print(f"Erro ao carregar o modelo: {e}")
            self.model_loaded.emit(None) # Emite None em caso de erro