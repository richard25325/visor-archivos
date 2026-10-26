"""Punto de entrada de la aplicación."""
import sys
import os
from PySide6.QtWidgets import QApplication
from visor_documental.ui import MainWindow

if __name__ == "__main__":
    if not getattr(sys, "frozen", False) and sys.prefix == sys.base_prefix and os.environ.get("VISOR_ALLOW_GLOBAL_PYTHON") != "1":
        raise SystemExit("Active el entorno virtual antes de ejecutar: .\\.venv\\Scripts\\Activate.ps1")
    application = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(application.exec())
