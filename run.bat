@echo off
REM Windows runner — use this if you're on Windows
call .venv\Scripts\activate.bat
echo Starting Yuno AI Agent Orchestration Platform on http://localhost:8000
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
