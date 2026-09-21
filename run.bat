@echo off
setlocal EnableDelayedExpansion
title AutoJurnal Launcher

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

:: Pastikan venv ada
if not exist "venv\Scripts\python.exe" (
    echo [INFO] Virtual environment belum dibuat. Menjalankan instalasi pertama kali...
    call install.bat
    exit /b
)

:: Cek apakah server sudah berjalan di port 8000
netstat -ano | findstr :8000 | findstr LISTENING >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] Server AutoJurnal sudah aktif. Membuka jendela aplikasi...
    goto OPEN_APP
)

echo Memulai server backend AutoJurnal...
start /B "" "venv\Scripts\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

:: Tunggu 2 detik agar uvicorn mulai mendengarkan
timeout /t 2 /nobreak >nul

:OPEN_APP
:: Buka di Edge App Window jika ada
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" (
    start "" "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" --app=http://localhost:8000 --user-data-dir="%USERPROFILE%\.autojurnal\app_profile"
    exit /b
)
if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" (
    start "" "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" --app=http://localhost:8000 --user-data-dir="%USERPROFILE%\.autojurnal\app_profile"
    exit /b
)
:: Buka di Chrome App Window jika ada
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles%\Google\Chrome\Application\chrome.exe" --app=http://localhost:8000 --user-data-dir="%USERPROFILE%\.autojurnal\app_profile"
    exit /b
)
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" --app=http://localhost:8000 --user-data-dir="%USERPROFILE%\.autojurnal\app_profile"
    exit /b
)

:: Fallback ke browser default
start http://localhost:8000
