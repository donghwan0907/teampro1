@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title SafeLease Supabase Setup

if exist ".env" goto open_env
copy /y ".env.example" ".env" >nul
if errorlevel 1 goto error

:open_env
echo.
echo 1. Find the SUPABASE_SECRET_KEY= line in Notepad.
echo 2. Paste your server Secret key after the equals sign.
echo 3. Save the file and close Notepad.
echo.
notepad ".env"
goto end

:error
echo [ERROR] Could not create the .env file.
pause

:end
endlocal
exit /b 0
