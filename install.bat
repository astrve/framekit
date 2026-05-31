@echo off
setlocal enabledelayedexpansion

echo.
echo  ============================================
echo   Swirrl v2.0.0 - Windows Installer
echo  ============================================
echo.

:: ── Python check ──────────────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.12+ from https://www.python.org
    goto :end_pause
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    if %%a lss 3 (
        echo [ERROR] Python 3.12+ required, found %PYVER%
        goto :end_pause
    )
    if %%a equ 3 if %%b lss 12 (
        echo [ERROR] Python 3.12+ required, found %PYVER%
        goto :end_pause
    )
)
echo [OK] Python %PYVER%

:: ── Virtual environment ────────────────────────────────────────────────────────
set VENV_DIR=%~dp0.venv
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [..] Creating virtual environment...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        goto :end_pause
    )
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment exists.
)

:: ── Install Swirrl ──────────────────────────────────────────────────────────
echo [..] Installing Swirrl...
"%VENV_DIR%\Scripts\pip.exe" install --upgrade pip >nul 2>&1
"%VENV_DIR%\Scripts\pip.exe" install -e "%~dp0."
if errorlevel 1 (
    echo [ERROR] Installation failed.
    goto :end_pause
)
echo [OK] Swirrl installed.

:: ── Verify ────────────────────────────────────────────────────────────────────
"%VENV_DIR%\Scripts\swirrl.exe" --version >nul 2>&1
if errorlevel 1 (
    echo [WARN] swirrl binary not found in venv.
) else (
    for /f "delims=" %%v in ('"%VENV_DIR%\Scripts\swirrl.exe" --version 2^>^&1') do echo [OK] %%v
)

:: ── Optional dependencies ─────────────────────────────────────────────────────
echo.
echo  Optional dependencies (recommended):
echo    - MKVToolNix ^(mkvmerge^) : required by CleanMKV
echo    - FFmpeg                  : required by Encode/Screenshot
echo    - MediaInfo               : required by metadata inspection
echo    - rclone                  : required by Seedbox
echo.
echo  Install method:
echo    [1] winget  ^(recommended^)
echo    [2] Chocolatey ^(choco^)
echo    [3] Skip
echo.
set /p DEP_CHOICE=Your choice [1/2/3]:

if "%DEP_CHOICE%"=="1" goto :deps_prompt
if "%DEP_CHOICE%"=="2" goto :deps_prompt
goto :verify_deps

:deps_prompt
set INSTALL_MKV=Y
set INSTALL_FFMPEG=Y
set INSTALL_MEDIAINFO=Y
set INSTALL_RCLONE=Y
set /p INSTALL_MKV=Install MKVToolNix (mkvmerge)? [Y/n]:
set /p INSTALL_FFMPEG=Install FFmpeg? [Y/n]:
set /p INSTALL_MEDIAINFO=Install MediaInfo? [Y/n]:
set /p INSTALL_RCLONE=Install rclone? [Y/n]:
if "%DEP_CHOICE%"=="1" goto :install_winget
goto :install_choco

:install_winget
echo.
if /I not "%INSTALL_MKV%"=="N" (
    echo [..] Installing MKVToolNix via winget...
    winget install MKVToolNix.MKVToolNix --silent
    if errorlevel 1 echo [WARN] MKVToolNix install may have failed. Check manually.
)
if /I not "%INSTALL_FFMPEG%"=="N" (
    echo [..] Installing FFmpeg via winget...
    winget install Gyan.FFmpeg --silent
    if errorlevel 1 echo [WARN] FFmpeg install may have failed. Check manually.
)
if /I not "%INSTALL_MEDIAINFO%"=="N" (
    echo [..] Installing MediaInfo via winget...
    winget install MediaArea.MediaInfo.GUI --silent
    if errorlevel 1 echo [WARN] MediaInfo install may have failed. Check manually.
)
if /I not "%INSTALL_RCLONE%"=="N" (
    echo [..] Installing rclone via winget...
    winget install Rclone.Rclone --silent
    if errorlevel 1 echo [WARN] rclone install may have failed. Check manually.
)
echo [OK] winget installs requested.
goto :verify_deps

:install_choco
echo.
choco --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Chocolatey not found. Install from https://chocolatey.org/install
    goto :verify_deps
)
if /I not "%INSTALL_MKV%"=="N" (
    echo [..] Installing MKVToolNix via choco...
    choco install mkvtoolnix -y
)
if /I not "%INSTALL_FFMPEG%"=="N" (
    echo [..] Installing FFmpeg via choco...
    choco install ffmpeg -y
)
if /I not "%INSTALL_MEDIAINFO%"=="N" (
    echo [..] Installing MediaInfo via choco...
    choco install mediainfo -y
)
if /I not "%INSTALL_RCLONE%"=="N" (
    echo [..] Installing rclone via choco...
    choco install rclone -y
)
echo [OK] Chocolatey installs requested.

:verify_deps
echo.
echo  Dependency check:
where mkvmerge >nul 2>&1 && echo [OK] mkvmerge found || echo [WARN] mkvmerge not found
where ffmpeg >nul 2>&1 && echo [OK] ffmpeg found || echo [WARN] ffmpeg not found
where mediainfo >nul 2>&1 && echo [OK] mediainfo found || echo [WARN] mediainfo not found
where rclone >nul 2>&1 && echo [OK] rclone found || echo [WARN] rclone not found

:: ── Summary ───────────────────────────────────────────────────────────────────
echo.
echo  ============================================
echo   Installation complete!
echo  ============================================
echo.
echo  Run Swirrl:
echo    %VENV_DIR%\Scripts\swirrl.exe --help
echo.
echo  Add to PATH (run in PowerShell):
echo    $env:PATH += ";%VENV_DIR%\Scripts"
echo    [Environment]::SetEnvironmentVariable("PATH", $env:PATH, "User")
echo.

:end_pause
echo.
pause
endlocal
