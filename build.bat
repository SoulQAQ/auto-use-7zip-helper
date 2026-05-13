@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

cd /d "%~dp0"

set "VENV_PY=.venv\Scripts\python.exe"
set "APP_NAME=自动打包器"

echo [信息] 正在检查环境...
call setup.bat
if errorlevel 1 (
    echo [错误] 环境检查失败，已中止打包。
    pause
    exit /b 1
)

"%VENV_PY%" -c "import PyInstaller" >nul 2>nul
if errorlevel 1 (
    echo [信息] 正在安装 PyInstaller...
    "%VENV_PY%" -m pip --disable-pip-version-check install pyinstaller
    if errorlevel 1 (
        echo [错误] PyInstaller 安装失败。
        pause
        exit /b 1
    )
) else (
    echo [信息] PyInstaller 已安装，跳过安装步骤。
)

if exist "build" (
    echo [信息] 正在清理 build 目录...
    rmdir /s /q "build"
)
if exist "dist" (
    echo [信息] 正在清理 dist 目录...
    rmdir /s /q "dist"
)

echo [信息] 正在打包，请稍候...
"%VENV_PY%" -m PyInstaller --noconfirm --clean "自动打包器.spec"
if errorlevel 1 (
    echo [错误] 打包失败。
    pause
    exit /b 1
)

if not exist "dist\%APP_NAME%.exe" (
    echo [错误] 打包命令已执行，但未找到输出文件：dist\%APP_NAME%.exe
    echo [错误] 请检查 build 日志与杀毒软件隔离区。
    pause
    exit /b 1
)

set "DIST_ABS=%CD%\dist"

echo.
echo [成功] 打包完成：dist\%APP_NAME%.exe
echo [路径] 输出目录：%DIST_ABS%
pause
