@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d D:\Desktop\HQmdstem\agent
echo Starting HQmdstem AI Assistant...
echo Browser will open at http://127.0.0.1:7860
C:\Users\yhq18\miniconda3\envs\gpumdkit\python.exe app.py
pause
