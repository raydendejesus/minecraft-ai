@echo off
rem Carry on with the training jobs frozen by PAUSE_TRAINING.bat, exactly where they stopped.
cd /d O:\MinecraftAI
venv\Scripts\python.exe pause_training.py resume
pause
