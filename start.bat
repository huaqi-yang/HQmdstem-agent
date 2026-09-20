@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

set "PYTHON=python"
if exist "%USERPROFILE%\miniconda3\envs\gpumdkit\python.exe" set "PYTHON=%USERPROFILE%\miniconda3\envs\gpumdkit\python.exe"

echo Starting HQmdstem AI Assistant...
echo Browser will open at http://127.0.0.1:7860
"%PYTHON%" app.py
pause
