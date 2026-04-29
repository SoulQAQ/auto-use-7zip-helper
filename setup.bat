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

:: 1. 检查 py 启动器
where py >nul 2>nul
if errorlevel 1 (
    echo [错误] 未找到 py 启动器。
    pause
    exit /b 1
)

:: 2. 检查 Python 版本
py -3.12 -c "import sys" >nul 2>nul
if errorlevel 1 (
    echo [错误] 未检测到 Python 3.12。
    pause
    exit /b 1
)

:: 3. 创建虚拟环境
if not exist "%VENV_PY%" (
    echo [信息] 正在创建虚拟环境...
    py -3.12 -m venv "%VENV_DIR%"
)

:: 4. 验证虚拟环境版本（读取 pyvenv.cfg）
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
    py -3.12 -m venv "%VENV_DIR%"
)

:: 5. 升级基础工具
echo [信息] 正在升级 pip setuptools wheel...
"%VENV_PY%" -m pip install --upgrade pip setuptools wheel

:: 6. 安装依赖
if exist "%REQUIREMENTS%" (
    echo [信息] 正在安装依赖...
    "%VENV_PY%" -m pip install -r "%REQUIREMENTS%"
    copy /y "%REQUIREMENTS%" "%SNAPSHOT_FILE%" >nul
)

echo [成功] 环境准备完成。
exit /b 0