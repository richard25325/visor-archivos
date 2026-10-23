$ErrorActionPreference = "Stop"
if (-not (Test-Path -Path ".venv\Scripts\python.exe")) { py -3 -m venv .venv }
& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt
Write-Host "Entorno virtual preparado. Ejecute .\run.ps1"
