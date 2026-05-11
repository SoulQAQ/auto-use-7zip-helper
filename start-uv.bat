@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

cd /d "%~dp0"
title Auto Packer - UV Launcher

set "MAIN_SCRIPT=script\gui.py"
set "REQUIREMENTS=requirements.txt"
set "VENV_DIR=.venv"

echo ========================================
echo   Auto Packer (UV)
echo ========================================
echo.

:: Check if uv is available
where uv >nul 2>nul
if errorlevel 1 (
    echo [ERROR] uv not found. Please install uv first:
    echo   pip install uv
    echo   or visit: https://github.com/astral-sh/uv
    echo.
    pause
    exit /b 1
)

:: Check main script
if not exist "%MAIN_SCRIPT%" (
    echo [ERROR] Main script not found: %MAIN_SCRIPT%
    echo.
    pause
    exit /b 1
)

:: Create virtual environment if not exists
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [INFO] Creating virtual environment with uv...
    uv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        echo.
        pause
        exit /b 1
    )
)

:: Install dependencies
echo [INFO] Installing dependencies with uv...
if exist "%REQUIREMENTS%" (
    uv pip install -r "%REQUIREMENTS%"
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        echo.
        pause
        exit /b 1
    )
) else (
    echo [WARNING] requirements.txt not found
    pause
    exit /b 1
)

:: Start application
echo.
echo [INFO] Starting application...
"%VENV_DIR%\Scripts\python.exe" "%MAIN_SCRIPT%"
set "APP_EXIT=%ERRORLEVEL%"

echo.
if not "%APP_EXIT%"=="0" (
    echo [ERROR] Application exited with code: %APP_EXIT%
    echo.
    pause
    exit /b %APP_EXIT%
)

endlocal
exit /b 0
