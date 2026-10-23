$ErrorActionPreference = "Stop"

if (-not (Test-Path -Path ".venv\Scripts\python.exe")) { & ".\setup.ps1" }
& ".venv\Scripts\python.exe" -m PyInstaller --noconfirm --windowed --name VisorDocumental --workpath build\pyinstaller --distpath dist app.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller no pudo completar la compilación." }
Write-Host "Ejecutable creado en .\dist\VisorDocumental\VisorDocumental.exe"
