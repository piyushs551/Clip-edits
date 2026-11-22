@echo off
rem DailyClip Editor launcher: finds Python 3.10+, makes .venv, installs deps, starts the app.
rem No PowerShell script activation needed.
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto have_venv
set PYCMD=
for %%V in (3.13 3.12 3.11 3.10) do (
  if not defined PYCMD (
    py -%%V -c "import sys" >nul 2>nul && set PYCMD=py -%%V
  )
)
if not defined PYCMD (
  echo Python 3.10 or newer was not found.
  echo Install it with:  winget install Python.Python.3.12
  echo Then close and reopen this window and run run.bat again.
  exit /b 1
)
%PYCMD% -m venv .venv || exit /b 1
:have_venv
".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" || (
  echo The .venv folder was made with an old Python. Delete the .venv folder and run run.bat again.
  exit /b 1
)
where ffmpeg >nul 2>nul || echo WARNING: ffmpeg not found on PATH. Install it with:  winget install Gyan.FFmpeg
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt || exit /b 1
".venv\Scripts\python.exe" app.py
