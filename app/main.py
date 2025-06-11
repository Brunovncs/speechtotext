import sys
from PySide6.QtWidgets import QApplication
# Supondo que estes imports estejam corretos para sua estrutura de pastas
from .app_window import TranscricaoApp 
from .ui.styles import MAIN_APP_STYLESHEET

def start_application():
    """
    Inicializa e executa a aplicação PySide6.
    """
    app = QApplication(sys.argv)
    
    # Aplicar o stylesheet principal
    app.setStyleSheet(MAIN_APP_STYLESHEET)
    
    window = TranscricaoApp()
    window.show()
    
    # Inicia o loop de eventos e retorna o código de status ao sair
    return app.exec()

# Este bloco agora permite que você ainda execute main.py diretamente para testes
if __name__ == "__main__":
    sys.exit(start_application())