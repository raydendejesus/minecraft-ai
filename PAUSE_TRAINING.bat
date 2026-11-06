@echo off
rem Freeze every training job while you play. Run RESUME_TRAINING.bat when you're done.
cd /d O:\MinecraftAI
venv\Scripts\python.exe pause_training.py pause
pause
