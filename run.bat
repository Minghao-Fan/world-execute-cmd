@echo off
rem ===========================================================================
rem  run.bat : one-click live terminal player -- ZERO prerequisites.
rem
rem  Double-click on any Windows machine and it plays. If a component is
rem  missing it is downloaded automatically into .tools\ (relative to this
rem  file, never touching the system):
rem    1/4 Python      -> reuse .venv, else a system Python >= 3.12, else a
rem                       portable embedded Python 3.12 downloaded to .tools\python
rem    2/4 ffmpeg      -> reuse PATH ffmpeg, else a portable build to .tools\ffmpeg
rem    3/4 song check  -> needs your own input\song.mp3 (copyrighted, not in repo)
rem    4/4 play        -> first-run also converts the song to 22k mono and
rem                       generates audio features + stand-in dancer caches
rem
rem  usage: run.bat [--song input\song.mp3] [--cols 160] [--rows 46] [--t0 0]
rem         run.bat --clean            delete regenerable caches, then rebuild+play
rem         run.bat --chat-rows 6    (chat overlay rows at the bottom, default 10)
rem         run.bat --render half    (picture renderer: braille 2x4 dots [default] / half blocks)
rem         run.bat --dot-offset 24    (braille adaptive dot offset, default 16, higher = thinner)
rem         run.bat --no-audio --full-post --t0 118
rem  keys:  q quit | space pause | left/right -/+5s | [ ] -/+1s | p screenshot | h hint
rem  large regenerable caches can be wiped on demand with cleaner.bat.
rem  NOTE for editors: inside any ( ... ) block never put unpaired '!' or '()'
rem  parens inside quoted commands - delayed expansion swallows '!' and cmd's
rem  brace pairing can truncate the line (see git log: pip + ffmpeg fixes).
rem ===========================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"
set "SRC=%~dp0src"
set "PY="

rem  --clean is consumed here (clears regenerable caches); the rest is passed
rem  straight through to the player.
set "CLEAN="
set "EXTRA="
:argloop
if "%~1"=="" goto :argdone
if /i "%~1"=="--clean" (set "CLEAN=1") else (set "EXTRA=!EXTRA! %~1")
shift
goto :argloop
:argdone

rem ============================ [1/4] Python ================================
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY=%~dp0.venv\Scripts\python.exe"
    goto :py_ready
)

set "SYS_PY="
rem  try `python` first (most common). Store "App Execution Aliases" live under
rem  %LOCALAPPDATA%\Microsoft\WindowsApps and fail at runtime when the app is
rem  missing, so any result there is discarded and we fall through to the
rem  embedded Python instead.
where python >nul 2>nul
if not errorlevel 1 for /f "delims=" %%p in ('python -c "import sys;print(sys.executable)" 2^>nul') do set "SYS_PY=%%p"
if defined SYS_PY (echo %SYS_PY%|findstr /i "WindowsApps" >nul && set "SYS_PY=")
if not defined SYS_PY (
    where py >nul 2>nul
    if not errorlevel 1 for /f "delims=" %%p in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do set "SYS_PY=%%p"
    if defined SYS_PY (echo %SYS_PY%|findstr /i "WindowsApps" >nul && set "SYS_PY=")
)
if defined SYS_PY ("%SYS_PY%" -c "import sys;sys.exit(0 if sys.version_info>=(3,12) else 1)" >nul 2>&1) || set "SYS_PY="
if defined SYS_PY (
    echo [1/4] using system Python: %SYS_PY%
    if not exist "%~dp0.venv" "%SYS_PY%" -m venv "%~dp0.venv" || goto :fail
    set "PY=%~dp0.venv\Scripts\python.exe"
    "!PY!" -m pip install --disable-pip-version-check -r "%~dp0requirements.txt" || goto :fail
    goto :py_ready
)

echo [1/4] no system Python found - getting embedded Python 3.12 ...
call :get_embed_py
if errorlevel 1 goto :fail
set "PY=%~dp0.tools\python\python.exe"

:py_ready

rem ============================ [2/4] ffmpeg ================================
set "FF="
where ffmpeg >nul 2>nul && set "FF=ffmpeg"
if not defined FF (
    if exist "%~dp0.tools\ffmpeg\bin\ffmpeg.exe" (
        set "FF=%~dp0.tools\ffmpeg\bin\ffmpeg.exe"
        set "WEC_FF=%~dp0.tools\ffmpeg\bin"
    ) else (
        echo [2/4] ffmpeg not found - downloading portable build ^(~115 MB, one-time^) ...
        powershell -NoProfile -ExecutionPolicy Bypass -Command "$u1='https://gh-proxy.com/https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip';$u2='https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip';$d='%~dp0.tools';New-Item -ItemType Directory -Force -Path $d|Out-Null;$z=Join-Path $d 'ff.zip';[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;try{Invoke-WebRequest -Uri $u1 -OutFile $z -TimeoutSec 300 -ErrorAction Stop}catch{Invoke-WebRequest -Uri $u2 -OutFile $z -TimeoutSec 300 -ErrorAction Stop};Expand-Archive -Path $z -DestinationPath $d -Force;Remove-Item $z -Force;Get-ChildItem $d -Directory -Filter 'ffmpeg-*'|Rename-Item -NewName 'ffmpeg'" || goto :fail
        set "FF=%~dp0.tools\ffmpeg\bin\ffmpeg.exe"
        set "WEC_FF=%~dp0.tools\ffmpeg\bin"
    )
)

rem ============================ [3/4] song check ============================
if not exist "%~dp0input\song.mp3" (
    echo.
    echo live: input\song.mp3 not found.
    echo       run.bat finishes ALL environment setup anyway: it mints a silent
    echo       stand-in track so every cache builds and the picture plays.
    echo       Later, drop Mili - world.execute^(me^) into input\song.mp3 and
    echo       re-run - the stand-in caches are replaced automatically.
    if not exist "%~dp0input" mkdir "%~dp0input"
    echo [3/4] minting silent stand-in track ^(no song.mp3 yet^) ...
    "%FF%" -nostdin -v error -y -f lavfi -i "anullsrc=r=44100:cl=stereo" -t 211.9 "%~dp0input\song.mp3" || goto :fail
    echo 1 > "%~dp0src\world_execute_replica\assets\audio\.placeholder"
)
rem  a real song arrived while a stand-in was in place: rebuild every cache.
if exist "%~dp0input\song.mp3" if exist "%~dp0src\world_execute_replica\assets\audio\.placeholder" (
    echo [3/4] real song detected - replacing stand-in caches ...
    del /q "%~dp0src\world_execute_replica\assets\audio\song_mono22k.wav" 2>nul
    del /q "%~dp0src\world_execute_replica\tui\engine\audio_features.json" 2>nul
    rd /s /q "%~dp0src\world_execute_replica\tui\continuity\cache\h3_full_v1" 2>nul
    rd /s /q "%~dp0src\world_execute_replica\dancer\pv_cache" 2>nul
    del /q "%~dp0src\world_execute_replica\assets\audio\.placeholder" 2>nul
)

rem ============================ [4/4] assets + play ========================
rem  --clean: wipe regenerable caches BEFORE the checks so they rebuild.
if defined CLEAN (
    echo [3/4] --clean: clearing regenerable caches ...
    del /q "%~dp0src\world_execute_replica\assets\audio\song_mono22k.wav" 2>nul
    del /q "%~dp0src\world_execute_replica\tui\engine\audio_features.json" 2>nul
    rd /s /q "%~dp0src\world_execute_replica\tui\continuity\cache\h3_full_v1" 2>nul
    rd /s /q "%~dp0src\world_execute_replica\dancer\pv_cache" 2>nul
)
if exist "%~dp0src\world_execute_replica\assets\audio\.placeholder" (
    echo.
    echo       ^> no real song yet - playing the silent stand-in; add
    echo         input\song.mp3 and re-run to hear the audio.
    echo.
)
echo [3/4] checking runtime assets ...
if not exist "%~dp0src\world_execute_replica\assets\audio\song_mono22k.wav" (
    echo       converting song to 22k mono ...
    "%FF%" -nostdin -v error -y -i "%~dp0input\song.mp3" -ac 1 -ar 22050 "%~dp0src\world_execute_replica\assets\audio\song_mono22k.wav" || goto :fail
)
if not exist "%~dp0src\world_execute_replica\tui\engine\audio_features.json" (
    echo       generating audio features ...
    set "PYTHONPATH=%SRC%"
    "%PY%" -c "import sys;sys.path.insert(0,r'%~dp0src');sys.path.insert(0,r'%~dp0src\world_execute_replica\_shims');import world_execute_replica.tui.engine.music as m;m.table()" || goto :fail
)
if not exist "%~dp0src\world_execute_replica\tui\continuity\cache\h3_full_v1" (
    echo       generating stand-in dancer caches ^(one-time, ~30 s^) ...
    set "PYTHONPATH=%SRC%"
    "%PY%" "%~dp0src\world_execute_replica\dancer\placeholder.py" || goto :fail
)

echo.
echo [4/4] playing - the grid auto-fits your window width; maximize the
echo        window for the sharpest picture, or set a size with
echo        run.bat --cols 220 --rows 50.
echo.
set "PYTHONPATH=%SRC%"
"%PY%" -m world_execute_replica.live %EXTRA%
exit /b %errorlevel%

rem ---------------------------------------------------------------------------
:get_embed_py
set "EMB=%~dp0.tools\python"
if not exist "%EMB%\python.exe" (
    if not exist "%~dp0.tools" mkdir "%~dp0.tools"
    echo       downloading https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$u='https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip';$d='%~dp0.tools';$z=Join-Path $d 'py.zip';[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;Invoke-WebRequest -Uri $u -OutFile $z;Expand-Archive -Path $z -DestinationPath '%EMB%' -Force;Remove-Item $z -Force" || exit /b 1
    rem  enable site-packages in the embedded python (comment was "#import site")
    for %%f in ("%EMB%\python*._pth") do (
        powershell -NoProfile -ExecutionPolicy Bypass -Command "$p='%%f';$c=[IO.File]::ReadAllText($p).Replace([string][char]0xFEFF,'').Replace('#import site','import site');[IO.File]::WriteAllText($p,$c,(New-Object Text.UTF8Encoding $false))"
    )
)
"%EMB%\python.exe" -m pip --version >nul 2>&1 || (
    echo       installing pip + dependencies ^(pillow, numpy^) ...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%EMB%\get-pip.py'" || exit /b 1
    "%EMB%\python.exe" "%EMB%\get-pip.py" --no-warn-script-location --disable-pip-version-check || exit /b 1
    del /q "%EMB%\get-pip.py" 2>nul
)
"%EMB%\python.exe" -m pip install --quiet --disable-pip-version-check -r "%~dp0requirements.txt" || exit /b 1
exit /b 0

:fail
echo.
echo live: setup failed. See the message above.
pause
exit /b 1
