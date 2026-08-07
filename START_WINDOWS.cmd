@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title SafeLease

if "%SAFELEASE_TEST_ONLY%"=="1" goto test_ok
if exist ".env" goto check_venv

echo.
echo SafeLease needs a one-time Supabase setting for cloud login storage.
echo You can skip it and use local SQLite storage.
choice /C YN /N /M "Configure Supabase now? [Y/N]: "
if errorlevel 2 goto check_venv
call "CONFIGURE_SUPABASE.cmd"

:check_venv
if exist ".venv\Scripts\python.exe" goto activate_venv

echo.
echo [1/3] Preparing the Python environment...
where py >nul 2>nul
if errorlevel 1 goto create_with_python
py -3 -m venv .venv
if exist ".venv\Scripts\python.exe" goto activate_venv

:create_with_python
where python >nul 2>nul
if errorlevel 1 goto python_missing
python -m venv .venv
if not exist ".venv\Scripts\python.exe" goto error

:activate_venv
call ".venv\Scripts\activate.bat"
if errorlevel 1 goto error

python -c "import fastapi,pandas,pydantic_settings,uvicorn" >nul 2>nul
if not errorlevel 1 goto packages_ready

echo [2/3] Installing required packages. This is needed only once...
python -m pip install -r requirements.txt
if errorlevel 1 goto error
goto open_site

:packages_ready
echo [2/3] Required packages are ready.

:open_site
echo [3/3] Opening http://127.0.0.1:8000
echo Press Ctrl+C in this window to stop the site.
start "" "http://127.0.0.1:8000"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
goto end

:python_missing
echo.
echo [ERROR] Python 3 is not installed or is not available in PATH.
echo Install Python from https://www.python.org/downloads/windows/
goto pause_error

:error
echo.
echo [ERROR] SafeLease could not start.
echo Check the message above and your internet connection.

:pause_error
pause
goto end

:test_ok
echo START_SAFELEASE_CMD_OK

:end
endlocal
exit /b 0
