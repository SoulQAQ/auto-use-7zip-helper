# Python 桌面应用项目架构模板

本文档总结当前项目的通用工程方案，可作为下一个项目的架构起点。涵盖：前后端架构、pywebview 集成、依赖管理、虚拟环境、EXE 打包、配置管理等通用模块。

---

## 一、项目结构

```
project-root/
├── script/                 # Python 后端脚本
│   ├── gui.py              # GUI 入口与 API 桥接
│   └── core.py             # 核心业务逻辑（可选拆分）
├── webui/                  # 前端静态资源
│   ├── index.html          # 主页面入口
│   └── help.html           # 帮助页面（可选）
├── config/                 # 配置文件目录
│   └── setting.yaml        # 主配置文件
├── .venv/                  # Python 虚拟环境（由 setup.bat 创建）
├── requirements.txt        # 依赖清单
├── setup.bat               # 环境安装脚本
├── start.bat               # 启动脚本
├── build.bat               # 打包脚本
├── app.ico                 # 应用图标
└── README.md               # 项目说明
```

---

## 二、前后端架构

### 2.1 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    桌面应用程序                           │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐    pywebview API    ┌───────────────┐  │
│  │  前端 UI    │ ◄──────────────────► │  Python 后端  │  │
│  │  (HTML/JS)  │    JSON 序列化       │   (gui.py)    │  │
│  └─────────────┘                      └───────────────┘  │
│        │                                      │         │
│        ▼                                      ▼         │
│  ┌─────────────┐                      ┌───────────────┐  │
│  │  状态管理   │                      │  业务逻辑层   │  │
│  │  (JS State) │                      │  (core.py)    │  │
│  └─────────────┘                      └───────────────┘  │
│                                               │         │
│                                               ▼         │
│                                       ┌───────────────┐  │
│                                       │  配置 / 文件  │  │
│                                       │  (YAML/JSON)  │  │
│                                       └───────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 2.2 技术栈

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| 前端 | HTML + CSS + Vanilla JS | 无框架依赖，轻量级 |
| 后端 | Python 3.12 | 主语言 |
| GUI 框架 | pywebview | 嵌入式 WebView，跨平台 |
| 配置 | PyYAML | YAML 配置文件读写 |
| 打包 | PyInstaller | 生成 Windows EXE |

### 2.3 前后端通信机制

**后端暴露 API 类：**

```python
# script/gui.py
import webview

class AppApi:
    """暴露给前端的 API 接口"""
    
    def get_initial_state(self, payload=None):
        """返回初始状态"""
        return {
            'input_path': '',
            'output_path': '',
            # ... 其他状态
        }
    
    def do_something(self, payload):
        """执行操作"""
        # 业务逻辑
        return {'success': True, 'message': '操作成功'}

def main():
    api = AppApi()
    window = webview.create_window(
        '应用标题',
        url='webui/index.html',
        js_api=api,           # 暴露 API 给前端
        width=1120,
        height=660,
        min_size=(980, 650),
        text_select=True,
    )
    webview.start(debug=False)
```

**前端调用后端 API：**

```javascript
// webui/index.html
async function callApi(method, payload = {}) {
    if (!window.pywebview || !window.pywebview.api) {
        throw new Error('pywebview API 不可用');
    }
    return window.pywebview.api[method](payload);
}

// 使用示例
async function bootstrap() {
    const state = await callApi('get_initial_state');
    console.log(state);
}

// 监听 pywebview 就绪事件
window.addEventListener('pywebviewready', bootstrap);
```

---

## 三、Python 虚拟环境管理

### 3.1 环境安装脚本 (setup.bat)

```batch
@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

cd /d "%~dp0"
title 应用名称 - 环境安装器

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
"%VENV_PY%" -m pip install --upgrade pip setuptools wheel

:: 6. 安装依赖
if exist "%REQUIREMENTS%" (
    "%VENV_PY%" -m pip install -r "%REQUIREMENTS%"
    copy /y "%REQUIREMENTS%" "%SNAPSHOT_FILE%" >nul
)

echo [成功] 环境准备完成。
exit /b 0
```

### 3.2 依赖快照机制

- 在 `.venv/` 目录下保存 `.requirements.snapshot` 文件
- 启动时对比 `requirements.txt` 与快照文件
- 若不一致则自动重新安装依赖

### 3.3 requirements.txt 示例

```
pyyaml
pywebview
# 其他业务依赖...
```

---

## 四、启动脚本 (start.bat)

```batch
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
```

---

## 五、EXE 打包 (build.bat)

### 5.1 打包脚本

```batch
@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

cd /d "%~dp0"

set "VENV_PY=.venv\Scripts\python.exe"
set "MAIN_SCRIPT=script\gui.py"
set "APP_NAME=应用程序名称"

:: 1. 调用 setup.bat 确保环境就绪
call setup.bat

:: 2. 安装 PyInstaller
"%VENV_PY%" -m pip install pyinstaller

:: 3. 清理旧文件
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

:: 4. 执行打包
"%VENV_PY%" -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name "%APP_NAME%" ^
  --add-data "webui;webui" ^
  --add-data "config;config" ^
  --add-data "app.ico;." ^
  --icon "app.ico" ^
  "%MAIN_SCRIPT%"

echo [成功] 打包完成：dist\%APP_NAME%.exe
pause
```

### 5.2 PyInstaller 关键参数

| 参数 | 说明 |
|------|------|
| `--onefile` | 打包为单个 EXE 文件 |
| `--windowed` | 无控制台窗口 |
| `--name` | 输出文件名 |
| `--add-data "src;dest"` | 添加数据文件（格式：源路径;目标路径） |
| `--icon` | 应用图标 |

### 5.3 运行时资源路径处理

```python
# script/gui.py
import sys
from pathlib import Path

if getattr(sys, 'frozen', False):
    # 打包后的运行环境
    APP_DIR = Path(sys.executable).resolve().parent
    RESOURCE_DIR = Path(getattr(sys, '_MEIPASS', APP_DIR)).resolve()
else:
    # 开发环境
    APP_DIR = Path(__file__).resolve().parent.parent
    RESOURCE_DIR = APP_DIR

# 资源路径
WEBUI_INDEX = RESOURCE_DIR / 'webui' / 'index.html'
CONFIG_PATH = APP_DIR / 'config' / 'setting.yaml'
```

---

## 六、配置管理

### 6.1 配置文件结构 (config/setting.yaml)

```yaml
# 应用配置
app_settings:
  language: zh-CN
  theme: light

# 用户设置
user_settings:
  input_path: ./rundata/input
  output_path: ./rundata/output
  last_conversion_type: type_a

# UI 提示信息
ui_tips:
  - 提示信息 1
  - 提示信息 2
```

### 6.2 配置读写工具函数

```python
# script/gui.py
import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / 'config' / 'setting.yaml'

DEFAULT_CONFIG = {
    'app_settings': {
        'language': 'zh-CN',
        'theme': 'light',
    },
    'user_settings': {
        'input_path': './rundata/input',
        'output_path': './rundata/output',
    },
}

def load_config():
    """加载配置，合并默认值"""
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    
    config = DEFAULT_CONFIG.copy()
    config.update(data)
    return config

def save_config(config):
    """保存配置"""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)
```

---

## 七、前端 UI 设计规范

### 7.1 目录结构

```
webui/
├── index.html      # 主页面（包含 HTML + CSS + JS）
└── help.html       # 帮助页面（可选）
```

### 7.2 页面结构模板

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>应用标题</title>
  <style>
    /* CSS 变量定义 */
    :root {
      --bg: #eef2f7;
      --panel: #ffffff;
      --text: #111827;
      --primary: #2563eb;
      --radius: 14px;
    }
    
    /* 全局样式 */
    * { box-sizing: border-box; }
    body { font-family: "Microsoft YaHei", sans-serif; }
    
    /* 组件样式 */
    .section { /* ... */ }
    .btn-primary { /* ... */ }
  </style>
</head>
<body>
  <div class="app">
    <!-- 顶部栏 -->
    <div class="topbar">...</div>
    
    <!-- 主工作区 -->
    <div class="workspace">...</div>
    
    <!-- 底部栏 -->
    <div class="bottom-bar">...</div>
  </div>
  
  <!-- 设置对话框 -->
  <div class="dialog-mask">...</div>
  
  <script>
    // 状态管理
    const state = { /* ... */ };
    
    // DOM 元素引用
    const els = { /* ... */ };
    
    // API 调用封装
    async function callApi(method, payload = {}) { /* ... */ }
    
    // 初始化
    window.addEventListener('pywebviewready', bootstrap);
  </script>
</body>
</html>
```

### 7.3 前端状态管理模式

```javascript
// 集中状态管理
const state = {
  conversionType: 'type_a',
  inputPath: '',
  outputPath: '',
  // ... 其他状态
};

// 状态更新函数
function updateState(key, value) {
  state[key] = value;
  renderUI();  // 触发 UI 重绘
}

// UI 渲染函数
function renderUI() {
  els.inputPath.value = state.inputPath;
  els.outputPath.value = state.outputPath;
  // ... 其他 UI 更新
}
```

---

## 八、文件对话框与路径处理

### 8.1 文件/文件夹选择

```python
# script/gui.py
import webview

class AppApi:
    def pick_folder(self, payload=None):
        """选择文件夹"""
        result = window.create_file_dialog(
            webview.FOLDER_DIALOG,
            directory=str(BASE_DIR)
        )
        if result:
            return {'path': result[0]}
        return {'path': None}
    
    def pick_file(self, payload=None):
        """选择文件"""
        result = window.create_file_dialog(
            webview.OPEN_DIALOG,
            directory=str(BASE_DIR),
            allow_multiple=False,
            file_types=['Excel 文件 (*.xlsx;*.xls)'],
        )
        if result:
            return {'path': result[0]}
        return {'path': None}
```

### 8.2 相对路径与绝对路径转换

```python
def normalize_relative_path(path_value):
    """将路径规范化为相对路径"""
    if not path_value:
        return ''
    
    path_obj = Path(path_value)
    if not path_obj.is_absolute():
        path_obj = (BASE_DIR / path_obj).resolve()
    else:
        path_obj = path_obj.resolve()
    
    try:
        return path_obj.relative_to(BASE_DIR).as_posix()
    except ValueError:
        return os.path.relpath(path_obj, BASE_DIR).replace('\\', '/')

def resolve_config_path(path_value):
    """将相对路径解析为绝对路径"""
    if not path_value:
        return ''
    return str((BASE_DIR / path_value).resolve())
```

---

## 九、错误处理与日志

### 9.1 API 错误处理模式

```python
class AppApi:
    def do_something(self, payload):
        try:
            # 业务逻辑
            result = process_data(payload)
            return {'success': True, 'data': result}
        except FileNotFoundError as e:
            return {'success': False, 'message': f'文件不存在：{e}'}
        except Exception as e:
            return {'success': False, 'message': f'操作失败：{str(e)}'}
```

### 9.2 前端错误处理

```javascript
async function handleAction() {
  try {
    const result = await callApi('do_something', { param: 'value' });
    if (!result.success) {
      setStatus(result.message, 'error');
      return;
    }
    setStatus('操作成功', 'success');
  } catch (error) {
    setStatus(error.message || String(error), 'error');
  }
}
```

---

## 十、快速启动清单

创建新项目时，按以下步骤操作：

### 10.1 初始化项目

1. 创建项目目录结构
2. 复制 `setup.bat`、`start.bat`、`build.bat` 到项目根目录
3. 创建 `requirements.txt` 并填写依赖
4. 创建 `config/setting.yaml` 配置文件
5. 创建 `webui/index.html` 前端页面
6. 创建 `script/gui.py` 后端入口

### 10.2 修改配置

- 修改 `setup.bat` 中的 `title` 和应用名称
- 修改 `start.bat` 中的 `MAIN_SCRIPT` 路径（如需要）
- 修改 `build.bat` 中的 `APP_NAME`
- 更新 `requirements.txt` 依赖列表
- 更新 `config/setting.yaml` 配置项

### 10.3 开发流程

```batch
# 1. 安装环境
setup.bat

# 2. 开发调试
start.bat

# 3. 打包发布
build.bat
```

---

## 十一、常见问题与解决方案

### 11.1 pywebview API 不可用

**问题**：前端调用 `window.pywebview.api` 时报错

**解决**：
- 确保通过 `start.bat` 或 `python script/gui.py` 启动
- 监听 `pywebviewready` 事件后再调用 API
- 检查后端 `js_api` 参数是否正确传递

### 11.2 打包后资源文件找不到

**问题**：EXE 运行时找不到 `webui/` 或 `config/` 目录

**解决**：
- 使用 `sys.frozen` 和 `_MEIPASS` 判断运行环境
- 确保 PyInstaller 的 `--add-data` 参数正确
- Windows 下路径分隔符使用分号 `;`

### 11.3 虚拟环境版本不匹配

**问题**：系统安装了多个 Python 版本

**解决**：
- `setup.bat` 使用 `py -3.12` 明确指定版本
- 检查 `pyvenv.cfg` 中的 `version` 字段
- 必要时删除 `.venv/` 重新创建

---

## 十二、参考文件

| 文件 | 说明 |
|------|------|
| [`setup.bat`](setup.bat) | 环境安装脚本 |
| [`start.bat`](start.bat) | 启动脚本 |
| [`build.bat`](build.bat) | 打包脚本 |
| [`script/gui.py`](script/gui.py) | GUI 入口与 API 桥接 |
| [`webui/index.html`](webui/index.html) | 前端页面 |
| [`config/setting.yaml`](config/setting.yaml) | 配置文件 |
| [`requirements.txt`](requirements.txt) | 依赖清单 |

---

本文档提供了完整的 Python 桌面应用项目架构模板，可直接用于新项目的初始化和开发。
