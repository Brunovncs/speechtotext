import sys
from PySide6.QtWidgets import QApplication
from .app_window import Speech2TextApp 
from .ui.styles import MAIN_APP_STYLESHEET

def start_application():
    """
    Inicializa e executa a aplicação PySide6.
    """
    app = QApplication(sys.argv)
    
    # Aplicar o stylesheet principal
    app.setStyleSheet(MAIN_APP_STYLESHEET)
    
    window = Speech2TextApp()
    window.show()
    
    # Inicia o loop de eventos e retorna o código de status ao sair
    return app.exec()

if __name__ == "__main__":
    sys.exit(start_application())