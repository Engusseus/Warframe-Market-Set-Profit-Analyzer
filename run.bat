@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%SCRIPT_DIR%.venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "CLI_EXE=%VENV_DIR%\Scripts\wf-market-analyzer.exe"

cd /d "%SCRIPT_DIR%"

if exist "%CLI_EXE%" (
  "%CLI_EXE%" %*
  exit /b %errorlevel%
) else if exist "%PYTHON_EXE%" (
  "%PYTHON_EXE%" -m wf_market_analyzer %*
  exit /b %errorlevel%
) else (
  echo No installed analyzer was found in "%VENV_DIR%".
  echo This launcher does not create environments or install packages during startup.
  echo Create .venv and install the project explicitly first; see README.md.
  exit /b 1
)
