@echo off
echo ===================================
echo Warframe Market Set Profit Analyzer
echo ===================================
echo.

REM Check if Python is installed
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed or not in PATH.
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

REM Check if virtual environment exists, create if it doesn't
if not exist venv (
    echo Setting up virtual environment...
    python -m venv venv
    echo Virtual environment created.
)

REM Activate virtual environment and install dependencies
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing required packages...
pip install -r requirements.txt > nul 2>&1

echo.
echo Running Warframe Market Analyzer...
echo Results will be saved to set_profit_analysis.csv
echo.
python wf_market_analyzer.py

echo.
echo Analysis complete! 
echo.
echo Results saved to: %CD%\set_profit_analysis.csv
echo.
pause
