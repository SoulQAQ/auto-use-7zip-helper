# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

自动打包器 (Auto Packaging Tool) - A Windows desktop application that encrypts files/folders into double-layer compressed packages. It generates random passwords, creates encrypted 7z archives, then packages them into non-encrypted zip files.

## Development Commands

```bash
# Install environment (requires Python 3.12)
setup.bat

# Launch application
start.bat

# Package to EXE (if build.bat exists)
build.bat

# Run Python backend directly
.venv/Scripts/python.exe script/gui.py
```

## Architecture

### Frontend-Backend Communication
- **pywebview** bridges Python backend with HTML/JS frontend
- Backend exposes `AppApi` class methods to frontend via `js_api` parameter
- Frontend calls API via `window.pywebview.api[method](payload)`
- All API returns: `{success: bool, data: any, message: str}`

### Key Files
- `script/gui.py`: GUI entry point, AppApi class with frontend-callable methods
- `script/core.py`: Core business logic (7z commands, password generation, packaging workflow)
- `webui/index.html`: Single-file frontend (HTML + CSS + JS)
- `config/setting.yaml`: Application settings (7z path, text types, user preferences)

### Runtime Path Handling
The app handles paths differently in dev vs. packaged EXE:
```python
if getattr(sys, 'frozen', False):
    APP_DIR = Path(sys.executable).resolve().parent
    RESOURCE_DIR = Path(getattr(sys, '_MEIPASS', APP_DIR)).resolve()
else:
    APP_DIR = Path(__file__).resolve().parent.parent
    RESOURCE_DIR = APP_DIR
```

### Packaging Workflow (core.py)
1. Generate 10-char random password (A-Za-z0-9)
2. Create encrypted 7z archive with `-mhe=on` (filename encryption)
3. Create password hint file: `解压：{password}.txt` (full-width colon for Windows compatibility)
4. Create text file if content provided
5. Package all into zip with `-mx=0` (storage mode, no compression)
6. Clean up temp directory

### Configuration Structure
```yaml
app_settings:
  language: zh-CN
  seven_zip_path: path/to/7z.exe
text_types:
  - label: 说明文本
    value: 说明文本
user_settings:
  last_text_type: 说明文本
  auto_delete_source: false
```

## Dependencies
- Python 3.12 (required)
- pyyaml: YAML config parsing
- pywebview: Desktop GUI framework
- 7-Zip: External dependency for compression (path configured in setting.yaml)

## Important Notes

- Password file uses full-width colon `：` (U+FF1A) to avoid Windows filename issues
- 7z commands use `creationflags=subprocess.CREATE_NO_WINDOW` on Windows to hide console
- Frontend uses `pywebviewready` event before calling API; fallback setTimeout check at 100ms
- Single file drag auto-fills archive name from file basename