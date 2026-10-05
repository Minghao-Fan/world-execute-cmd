@echo off
rem ===========================================================================
rem  sync.bat : commit all changes and push to GitHub over SSH
rem
rem  usage: sync.bat ["commit message"]          (default: "update <date> <time>")
rem
rem  requires:
rem    - git in PATH
rem    - an ssh key registered on GitHub (ssh -T git@github.com to verify)
rem    - a remote "origin" configured (git remote add origin git@github.com:USER/REPO.git)
rem
rem  run from anywhere; always operates on the folder this file lives in.
rem ===========================================================================
setlocal
cd /d "%~dp0"

git --version >nul 2>nul || (echo sync: git not found on PATH & goto :fail)
git rev-parse --is-inside-work-tree >nul 2>nul || (echo sync: not a git repository & goto :fail)
git remote get-url origin >nul 2>nul || (echo sync: no remote "origin" configured & goto :fail)

set "MSG=%~1"
if not defined MSG set "MSG=update %DATE:/=-% %TIME::=-%"

echo [sync] staging changes ...
git add -A
git commit -m "%MSG%" || (echo sync: nothing to commit, or commit failed. & goto :done)
echo [sync] pushing to origin over ssh ...
git push origin HEAD || goto :fail

echo.
echo [sync] pushed to origin (HEAD).
goto :done

:fail
echo.
echo sync: failed. See the message above.
echo       - push over ssh needs your key registered on GitHub and an ssh-agent running
echo       - verify with: ssh -T git@github.com
pause
exit /b 1

:done
exit /b 0
