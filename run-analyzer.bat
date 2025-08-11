@echo off
REM Warframe Market Set Profit Analyzer Launcher (Streamlit UI version)

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

REM Install dependencies (including Streamlit and others)
pip install -r requirements.txt
pip install streamlit plotly scikit-learn streamlit-lottie

REM Run the Streamlit app
streamlit run app.py

pause
