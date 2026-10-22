@echo off
cd /d "%~dp0"
"koita_stage1\.venv\Scripts\python.exe" release.py %*
pause
