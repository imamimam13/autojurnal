@echo off
title Hentikan AutoJurnal

echo Menghentikan server AutoJurnal...

:: 1. Hentikan berdasarkan port 8000
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)

:: 2. Hentikan proses python yang menjalankan uvicorn
wmic process where "CommandLine like '%%backend.main:app%%'" Call Terminate >nul 2>&1

echo.
echo [OK] Server AutoJurnal telah dihentikan.
timeout /t 2 >nul
