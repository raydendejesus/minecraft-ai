@echo off
cd /d "%~dp0"
start "" http://localhost:8842
venv\Scripts\python.exe neural_view.py
pause
