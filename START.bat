@echo off
cd /d "%~dp0"
if not exist builder.pt (
  echo The Builder model isn't trained yet - training it now, takes about 5 minutes...
  venv\Scripts\python.exe train.py
)
start "" http://localhost:8840
venv\Scripts\python.exe app.py
pause
