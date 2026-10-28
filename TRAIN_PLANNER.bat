@echo off
cd /d "%~dp0"
echo Training the Survival Planner from scratch (about 12 minutes on the 3090)...
venv\Scripts\python.exe train.py --task planner --steps 16000
echo.
echo Testing it on simulated survival games:
venv\Scripts\python.exe plan.py
pause
