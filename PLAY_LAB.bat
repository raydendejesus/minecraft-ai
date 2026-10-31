@echo off
cd /d "%~dp0"
echo Opening the Redstone Lab with the 16-byte RAM. Takes a couple of minutes to build.
venv\Scripts\python.exe lab_play.py ram 4 8
pause
