from pathlib import Path
from PySide6.QtCore import QStandardPaths

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xlsm"}

def database_path() -> Path:
    location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    folder = Path(location or Path.home() / ".visor-documental")
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "catalogo.db"
