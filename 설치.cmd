@echo off
cd /d "%~dp0koita_stage1"
py -3 -m venv .venv
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo Installation complete. Run the launcher in the parent folder.
pause
exit /b 0
:failed
echo Installation failed. Install Python 3.11 or newer and retry.
pause
exit /b 1
