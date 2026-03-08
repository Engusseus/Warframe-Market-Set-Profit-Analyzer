@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%SCRIPT_DIR%.venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "CLI_EXE=%VENV_DIR%\Scripts\wf-market-analyzer.exe"

cd /d "%SCRIPT_DIR%"

where py >nul 2>nul
if %errorlevel%==0 goto found_python

where python >nul 2>nul
if %errorlevel%==0 goto found_python

echo Python 3 is required to bootstrap this project.
echo Install Python 3, then rerun run.bat.
exit /b 1

:found_python
if exist "%PYTHON_EXE%" goto venv_ready

echo Creating virtual environment in "%VENV_DIR%"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 -m venv "%VENV_DIR%"
) else (
  python -m venv "%VENV_DIR%"
)
if errorlevel 1 (
  echo Failed to create .venv.
  echo Make sure Python 3 is installed with venv support, then rerun run.bat.
  exit /b %errorlevel%
)

:venv_ready
echo Upgrading pip inside .venv...
"%PYTHON_EXE%" -m pip install --upgrade pip
if errorlevel 1 (
  echo Failed to upgrade pip inside .venv.
  exit /b %errorlevel%
)

echo Installing the analyzer into .venv...
"%PYTHON_EXE%" -m pip install --upgrade .
if errorlevel 1 (
  echo Failed to install the analyzer into .venv.
  exit /b %errorlevel%
)

if exist "%CLI_EXE%" (
  "%CLI_EXE%" %*
) else (
  "%PYTHON_EXE%" -m wf_market_analyzer %*
)
exit /b %errorlevel%
