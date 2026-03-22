@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0.venv-x64\Scripts\pythonw.exe" start "" "%~dp0.venv-x64\Scripts\pythonw.exe" -m app.main & exit /b 0
if exist "%~dp0.venv-x64\Scripts\python.exe" start "" "%~dp0.venv-x64\Scripts\python.exe" -m app.main & exit /b 0
start "" py -3 -m app.main
endlocal
