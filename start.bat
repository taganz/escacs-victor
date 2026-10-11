@echo off
rem Arranca el servidor en http://localhost:8000
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo Creando el entorno virtual...
    py -3 -m venv .venv || python -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements.txt
)
start "" http://localhost:8000
.venv\Scripts\python.exe -m server %*
