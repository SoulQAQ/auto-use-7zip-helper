@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

cd /d "%~dp0"

set "VENV_PY=.venv\Scripts\python.exe"
set "MAIN_SCRIPT=script\gui.py"
set "APP_NAME=自动打包器"

:: 1. 调用 setup.bat 确保环境就绪
echo [信息] 正在检查环境...
call setup.bat

:: 2. 安装 PyInstaller
echo [信息] 正在安装 PyInstaller...
"%VENV_PY%" -m pip install pyinstaller

:: 3. 清理旧文件
if exist "build" (
    echo [信息] 正在清理 build 目录...
    rmdir /s /q "build"
)
if exist "dist" (
    echo [信息] 正在清理 dist 目录...
    rmdir /s /q "dist"
)

:: 4. 执行打包
echo [信息] 正在打包，请稍候...
"%VENV_PY%" -m PyInstaller "自动打包器.spec"

echo.
echo [成功] 打包完成：dist\%APP_NAME%.exe
pause