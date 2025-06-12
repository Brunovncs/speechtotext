import sounddevice as sd

def get_audio_devices():
    """Consulta e retorna uma lista de dispositivos de entrada de áudio."""
    try:
        all_devices = sd.query_devices()
        input_devices = []
        
        print("Dispositivos de áudio disponíveis:")
        for idx, dev in enumerate(all_devices):
            if dev['max_input_channels'] > 0:
                input_devices.append((idx, dev))
                print(f"  {idx}: {dev['name']} - {dev['max_input_channels']} canais - {dev['default_samplerate']}Hz")
        
        return input_devices, all_devices
    except Exception as e:
        print(f"Erro ao listar microfones: {e}")
        return [], None