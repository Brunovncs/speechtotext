import time
import numpy as np
import sounddevice as sd
import soundfile as sf
from PySide6.QtCore import QThread, Signal

class RecordingThread(QThread):
    """Thread para gravação de áudio."""
    recording_finished = Signal(str, bool)
    recording_error = Signal(str)
    recording_update = Signal(int)
    
    def __init__(self, device_idx, output_path, devices, keep_audio=False):
        super().__init__()
        self.device_idx = device_idx
        self.output_path = output_path
        self.devices = devices
        self.should_stop = False
        self.keep_audio = keep_audio
        
    def stop_recording(self):
        """Para a gravação."""
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