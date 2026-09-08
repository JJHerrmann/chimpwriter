@echo off
setlocal
set "ROOT=C:\Users\jjzeg\Chimpwriter"
set "LOG=%TEMP%\Chimpwriter_launch.log"

if not exist "%ROOT%\chimpwriter.py" (
  echo ERROR: chimpwriter.py not found in %ROOT%
  pause
  exit /b 1
)

set "PYEXE="
if exist "%ROOT%\.venv\Scripts\python.exe" set "PYEXE=%ROOT%\.venv\Scripts\python.exe"
if not defined PYEXE (
  set "PYEXE=py"
  where py >nul 2>&1
  if %errorlevel% neq 0 set "PYEXE=python"
)

cd /d "%ROOT%"
"%PYEXE%" "%ROOT%\chimpwriter.py" > "%LOG%" 2>&1
if %errorlevel% neq 0 (
  echo Launch failed. Log:
  type "%LOG%"
  echo.
  pause
)
