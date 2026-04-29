@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

cd /d "%~dp0"

set "VENV_DIR=.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "MAIN_SCRIPT=script\gui.py"
set "REQUIREMENTS=requirements.txt"
set "SNAPSHOT_FILE=%VENV_DIR%\.requirements.snapshot"
set "SETUP_SCRIPT=setup.bat"

:: 检查是否需要重新安装依赖
set "NEED_SETUP="
if not exist "%VENV_PY%" set "NEED_SETUP=1"
if not exist "%SNAPSHOT_FILE%" set "NEED_SETUP=1"
if exist "%REQUIREMENTS%" (
    fc /b "%REQUIREMENTS%" "%SNAPSHOT_FILE%" >nul 2>nul
    if errorlevel 1 set "NEED_SETUP=1"
)

if defined NEED_SETUP (
    echo [信息] 检测到环境变化，正在准备环境...
    call "%SETUP_SCRIPT%"
)

:: 启动应用
"%VENV_PY%" "%MAIN_SCRIPT%"