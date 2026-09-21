@echo off
setlocal EnableDelayedExpansion
title AutoJurnal - Installer & Setup (Windows)

echo ======================================================
echo    🚀 Memulai Instalasi AutoJurnal (Windows Setup)
echo ======================================================
echo.

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

:: 1. Cek Python
echo [1/5] Memeriksa instalasi Python di Windows...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    py -3 --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Python tidak ditemukan!
        echo Silakan install Python 3.10 atau yang lebih baru dari https://www.python.org/
        echo Pastikan opsi "Add Python to PATH" dicentang saat instalasi.
        pause
        exit /b 1
    ) else (
        set "PY_CMD=py -3"
    )
) else (
    set "PY_CMD=python"
)
echo [OK] Python terdeteksi.

:: 2. Setup Virtual Environment
echo.
echo [2/5] Menyiapkan Virtual Environment (venv)...
if not exist "venv\Scripts\python.exe" (
    echo Membuat venv baru...
    %PY_CMD% -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Gagal membuat virtual environment.
        pause
        exit /b 1
    )
) else (
    echo Virtual environment sudah siap.
)

:: 3. Install Dependencies
echo.
echo [3/5] Menginstal dependensi library...
call venv\Scripts\python.exe -m pip install --upgrade pip -q
call venv\Scripts\pip.exe install -q -r backend\requirements.txt
if %errorlevel% neq 0 (
    echo [WARNING] Ada library yang gagal diinstal, melanjutkan...
) else (
    echo [OK] Semua library berhasil diinstal.
)

:: 4. Generate Windows Icon jika belum ada
echo.
echo [4/5] Menyiapkan App Icon Windows...
if exist "scripts\generate_icon.py" (
    venv\Scripts\python.exe scripts\generate_icon.py >nul 2>&1
)

:: 5. Buat .env dan Shortcut Desktop
echo.
echo [5/5] Membuat konfigurasi dan Shortcut Desktop...
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo [OK] File .env berhasil dibuat.
    )
)

:: Buat shortcut di Desktop via PowerShell
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$WshShell = New-Object -ComObject WScript.Shell; " ^
  "$DesktopPath = [Environment]::GetFolderPath('Desktop'); " ^
  "$Shortcut = $WshShell.CreateShortcut(\"$DesktopPath\AutoJurnal.lnk\"); " ^
  "$Shortcut.TargetPath = 'wscript.exe'; " ^
  "$Shortcut.Arguments = '\"%PROJECT_DIR%AutoJurnal.vbs\"'; " ^
  "$Shortcut.WorkingDirectory = '%PROJECT_DIR%'; " ^
  "if (Test-Path '%PROJECT_DIR%scripts\build\AppIcon.ico') { $Shortcut.IconLocation = '%PROJECT_DIR%scripts\build\AppIcon.ico,0' }; " ^
  "$Shortcut.Description = 'AutoJurnal - AI Academic Journal Generator'; " ^
  "$Shortcut.Save(); " >nul 2>&1

echo [OK] Shortcut 'AutoJurnal' berhasil ditambahkan ke Desktop Windows!

echo.
echo ======================================================
echo    🎉 Instalasi Selesai! AutoJurnal Siap Digunakan
echo ======================================================
echo.
echo Cara menjalankan AutoJurnal:
echo   1. Double-click icon shortcut 'AutoJurnal' di Desktop Anda
echo   2. ATAU double-click file 'run.bat' di folder ini
echo.
echo Untuk menghentikan aplikasi:
echo   - Double-click 'stop.bat'
echo.
pause
