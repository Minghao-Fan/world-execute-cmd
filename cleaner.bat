@echo off
rem ===========================================================================
rem  cleaner.bat : remove large regenerable process files on demand.
rem
rem  Double-click for a menu, or pass items directly:
rem     cleaner.bat all --yes        everything below, no prompts
rem     cleaner.bat audio            song 22k wav + audio features
rem     cleaner.bat dancer           stand-in dancer caches (h3_full_v1 + pv_cache)
rem     cleaner.bat pycache          all __pycache__ directories
rem     cleaner.bat preview          output\live diagnostic images
rem     cleaner.bat prerender        pre-rendered frame cache (output\prerender, if any)
rem
rem  Never touches: input\song.mp3, .venv, .tools, src code, git.
rem  After cleaning, just run run.bat -- it rebuilds what it needs.
rem ===========================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"
set "YES="
set "ITEMS="

:argloop
if "%~1"=="" goto :argdone
if /i "%~1"=="--yes" (set "YES=1") else (set "ITEMS=!ITEMS! %~1")
shift
goto :argloop
:argdone

rem  no items -> interactive menu
if "%ITEMS%"=="" (
    echo.
    echo  cleaner: remove large regenerable process files
    echo  ------------------------------------------------
    echo   1 audio     song 22k wav + audio features
    echo   2 dancer    stand-in dancer caches
    echo   3 pycache   __pycache__ folders under src
    echo   4 preview   output\live images
    echo   5 prerender pre-rendered frame cache
    echo   6 all       everything above
    echo   q quit
    echo.
    choice /c 123456q /n /m "  pick (1-6, q=quit): "
    if errorlevel 7 goto :quit
    if errorlevel 6 set "ITEMS= all"
    if errorlevel 5 if not errorlevel 6 set "ITEMS= prerender"
    if errorlevel 4 if not errorlevel 5 set "ITEMS= preview"
    if errorlevel 3 if not errorlevel 4 set "ITEMS= pycache"
    if errorlevel 2 if not errorlevel 3 set "ITEMS= dancer"
    if errorlevel 1 if not errorlevel 2 set "ITEMS= audio"
)

rem  confirm (unless --yes)
if not defined YES (
    echo.
    echo  about to remove: %ITEMS%
    set /p "OK=  continue? [y/N] "
    if /i not "!OK!"=="y" (
        echo  cancelled. Nothing was removed.
        goto :quit
    )
)

rem  run each item
for %%i in (%ITEMS%) do call :clean_%%i
echo.
echo  done. Run run.bat afterwards - it rebuilds what it needs.
goto :quit

:clean_audio
echo  [cleaner] audio caches ...
del /q "%~dp0src\world_execute_replica\assets\audio\song_mono22k.wav" 2>nul
del /q "%~dp0src\world_execute_replica\tui\engine\audio_features.json" 2>nul
exit /b 0

:clean_dancer
echo  [cleaner] dancer caches ...
rd /s /q "%~dp0src\world_execute_replica\tui\continuity\cache\h3_full_v1" 2>nul
rd /s /q "%~dp0src\world_execute_replica\dancer\pv_cache" 2>nul
exit /b 0

:clean_pycache
echo  [cleaner] __pycache__ folders ...
for /d /r "%~dp0src" %%d in (__pycache__) do if exist "%%d" rmdir /s /q "%%d"
exit /b 0

:clean_preview
echo  [cleaner] preview images (output\live) ...
if exist "%~dp0output\live" rmdir /s /q "%~dp0output\live"
exit /b 0

:clean_prerender
echo  [cleaner] pre-rendered frame cache (output\prerender) ...
if exist "%~dp0output\prerender" rmdir /s /q "%~dp0output\prerender"
exit /b 0

:clean_all
call :clean_audio
call :clean_dancer
call :clean_pycache
call :clean_preview
call :clean_prerender
exit /b 0

:quit
endlocal
exit /b 0
