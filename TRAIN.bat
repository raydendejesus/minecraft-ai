@echo off
cd /d "%~dp0"
echo Training the Builder from scratch (about 5 minutes on the 3090)...
echo To only learn your new corrections instead, use the Retrain button in the app.
venv\Scripts\python.exe train.py
pause
