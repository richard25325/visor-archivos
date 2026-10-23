# Visor documental institucional

Aplicación de escritorio para indexar y consultar bibliotecas PDF, DOCX y XLSX.

## Ejecución

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Seleccione una carpeta raíz, pulse **Indexar** y navegue por el árbol. La base SQLite se guarda en `%LOCALAPPDATA%\VisorDocumental\catalogo.db` y los documentos originales no se modifican.
