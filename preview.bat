@echo off
rem ===========================================================================
rem  preview.bat : render an offline preview PNG of the live terminal (no playback)
rem
rem  usage: preview.bat [t_seconds]          e.g. preview.bat 150   (default: 30)
rem  output: output\live\preview_<t>.png
rem ===========================================================================
setlocal
cd /d "%~dp0"
set "PY=%~dp0.venv\Scripts\python.exe"

if not exist "%PY%" (
    echo preview: .venv missing. Run live.bat once first to set it up.
    goto :fail
)

"%PY%" "%~dp0scripts\live_preview.py" %*
exit /b %errorlevel%

:fail
echo.
echo preview: failed. See the message above.
pause
exit /b 1
