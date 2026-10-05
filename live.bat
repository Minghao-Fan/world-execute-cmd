@echo off
rem ===========================================================================
rem  live.bat : one-click live terminal player (all paths relative -> runs anywhere)
rem
rem  usage: live.bat [--song input\song.mp3] [--cols 160] [--rows 46] [--t0 0]
rem         live.bat --no-audio --full-post --t0 118
rem  keys:  q quit | space pause | left/right -/+5s | [ ] -/+1s | p screenshot | h hint
rem
rem  first run (or after a fresh clone on another machine):
rem    1/3 creates .venv and installs requirements.txt
rem    2/3 converts input\song.mp3 to 22k mono, generates audio features
rem        and the stand-in dancer caches (one-time, ~30 s)
rem    3/3 plays
rem ===========================================================================
setlocal
cd /d "%~dp0"
set "PY=%~dp0.venv\Scripts\python.exe"
set "SRC=%~dp0src"

rem ---- [1/3] virtualenv + deps --------------------------------------------
if not exist "%PY%" (
    echo [1/3] creating .venv ...
    (py -3 -m venv "%~dp0.venv") || (python -m venv "%~dp0.venv") || goto :fail
    "%PY%" -m pip install --quiet --disable-pip-version-check -r "%~dp0requirements.txt" || goto :fail
)

rem ---- [2/3] one-time runtime assets --------------------------------------
echo [2/3] checking runtime assets ...
if not exist "%~dp0src\world_execute_replica\assets\audio\song_mono22k.wav" (
    where ffmpeg >nul 2>nul || (echo live: ffmpeg not found on PATH & goto :fail)
    ffmpeg -v error -y -i "%~dp0input\song.mp3" -ac 1 -ar 22050 "%~dp0src\world_execute_replica\assets\audio\song_mono22k.wav" || goto :fail
)
if not exist "%~dp0src\world_execute_replica\tui\engine\audio_features.json" (
    set "PYTHONPATH=%SRC%"
    "%PY%" -c "import sys;sys.path.insert(0,r'%~dp0src');sys.path.insert(0,r'%~dp0src\world_execute_replica\_shims');import world_execute_replica.tui.engine.music as m;m.table()" || goto :fail
)
if not exist "%~dp0src\world_execute_replica\tui\continuity\cache\h3_full_v1" (
    echo [3/3] generating stand-in dancer caches ^(one-time, ~30 s^) ...
    set "PYTHONPATH=%SRC%"
    "%PY%" "%~dp0src\world_execute_replica\dancer\placeholder.py" || goto :fail
)

rem ---- [3/3] play ----------------------------------------------------------
set "PYTHONPATH=%SRC%"
"%PY%" -m world_execute_replica.live %*
exit /b %errorlevel%

:fail
echo.
echo live: setup failed. See the message above.
pause
exit /b 1
