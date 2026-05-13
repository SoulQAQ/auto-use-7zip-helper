@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

cd /d "%~dp0"
title 自动打包器 - 环境安装器

set "VENV_DIR=.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "VENV_CFG=%VENV_DIR%\pyvenv.cfg"
set "REQUIREMENTS=requirements.txt"
set "SNAPSHOT_FILE=%VENV_DIR%\.requirements.snapshot"
set "PY_CMD="
set "NEED_INSTALL=0"

where py >nul 2>nul
if not errorlevel 1 (
    py -3.12 -c "import sys" >nul 2>nul
    if not errorlevel 1 set "PY_CMD=py -3.12"
)

if not defined PY_CMD (
    where python >nul 2>nul
    if errorlevel 1 (
        echo [错误] 未找到可用的 Python 3.12 运行环境（py / python）。
        pause
        exit /b 1
    )
    python -c "import sys; exit(0 if sys.version_info[:2]==(3,12) else 1)" >nul 2>nul
    if errorlevel 1 (
        echo [错误] 当前 python 不是 3.12，请安装 Python 3.12。
        pause
        exit /b 1
    )
    set "PY_CMD=python"
)

if not exist "%VENV_PY%" (
    echo [信息] 正在创建虚拟环境...
    %PY_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败。
        pause
        exit /b 1
    )
    set "NEED_INSTALL=1"
)

set "VENV_VER="
if exist "%VENV_CFG%" (
    for /f "tokens=1,* delims==" %%A in (%VENV_CFG%) do (
        set "KEY=%%A"
        set "VAL=%%B"
        set "KEY=!KEY: =!"
        if /i "!KEY!"=="version" (
            set "VENV_VER=!VAL!"
            set "VENV_VER=!VENV_VER: =!"
        )
    )
)

echo %VENV_VER% | findstr /b "3.12." >nul
if errorlevel 1 (
    echo [警告] 虚拟环境版本不匹配，正在重建...
    rmdir /s /q "%VENV_DIR%"
    %PY_CMD% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [错误] 重建虚拟环境失败。
        pause
        exit /b 1
    )
    set "NEED_INSTALL=1"
)

if not exist "%REQUIREMENTS%" (
    echo [成功] 环境准备完成（未找到 requirements.txt，跳过依赖安装）。
    exit /b 0
)

if exist "%SNAPSHOT_FILE%" (
    fc.exe /b "%REQUIREMENTS%" "%SNAPSHOT_FILE%" >nul 2>nul
    if errorlevel 1 set "NEED_INSTALL=1"
) else (
    set "NEED_INSTALL=1"
)

if "%NEED_INSTALL%"=="1" (
    echo [信息] 正在升级 pip setuptools wheel...
    "%VENV_PY%" -m pip --disable-pip-version-check install --upgrade pip setuptools wheel
    if errorlevel 1 (
        echo [错误] pip 基础工具升级失败。
        pause
        exit /b 1
    )

    echo [信息] 正在安装依赖...
    "%VENV_PY%" -m pip --disable-pip-version-check install -r "%REQUIREMENTS%"
    if errorlevel 1 (
        echo [错误] 安装依赖失败。
        pause
        exit /b 1
    )
    copy /y "%REQUIREMENTS%" "%SNAPSHOT_FILE%" >nul
) else (
    echo [信息] 依赖未变化，跳过安装。
)

echo [成功] 环境准备完成。
exit /b 0
