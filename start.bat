@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
echo Starting HQmdstem AI Assistant...
echo Browser will open at http://127.0.0.1:7860
python app.py
pause
