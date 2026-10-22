@echo off
cd /d "%~dp0koita_stage1"
".venv\Scripts\python.exe" app.py
if errorlevel 1 pause
