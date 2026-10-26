@echo off
cd /d "%~dp0"
"koita_stage1\.venv\Scripts\python.exe" "koita_stage1\ir52_app.py"
if errorlevel 1 pause
