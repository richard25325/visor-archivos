$ErrorActionPreference = "Stop"
if (-not (Test-Path -Path ".venv\Scripts\python.exe")) { & ".\setup.ps1" }
& ".venv\Scripts\python.exe" app.py
