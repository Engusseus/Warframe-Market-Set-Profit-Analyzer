@echo off
REM Warframe Market Set Profit Analyzer Launcher

REM Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Python is not installed. Please install Python 3.7 or higher and try again.
    pause
    exit /b 1
)

set VENV=venv

REM Create virtual environment if it doesn't exist
if not exist %VENV%\Scripts\python.exe (
    echo Creating virtual environment...
    python -m venv %VENV%
)

REM Activate virtual environment
call %VENV%\Scripts\activate.bat

REM Install dependencies
pip install -r requirements.txt

REM Run the analyzer
python wf_market_analyzer.py

pause
