@echo off
REM Windows setup script
echo =================================================================
echo   Yuno AI Agent Orchestration Platform -- Setup (Windows)
echo =================================================================

echo.
echo [1/4] Creating virtual environment...
python -m venv .venv

echo.
echo [2/4] Activating venv and installing dependencies...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo [3/4] Setting up .env file...
if not exist .env (
    copy .env.example .env
    echo   -^> Created .env from template. EDIT IT with your API keys before running!
) else (
    echo   -^> .env already exists. Skipping.
)

echo.
echo [4/4] Initializing database and seeding workflow templates...
python -m app.seed

echo.
echo =================================================================
echo   SETUP COMPLETE!
echo =================================================================
echo.
echo Next steps:
echo   1. Edit .env and fill in ANTHROPIC_API_KEY and TELEGRAM_BOT_TOKEN
echo   2. Run: run.bat
echo   3. Open: http://localhost:8000
echo.
