"""
自动打包器 GUI入口和API桥接模块

提供pywebview API接口，连接前端UI和后端核心逻辑。
"""

import json
import subprocess
import sys
import webview
from pathlib import Path
import yaml
from webview.dom import DOMEventHandler

from core import (
    process_packaging_with_disguise,
    delete_source_files,
    DISGUISE_TYPES,
    has_custom_template,
    set_default_template,
    remove_default_template,
    get_default_template_path
)


# ============================================================================
# 运行时路径处理
# ============================================================================
if getattr(sys, 'frozen', False):
    # PyInstaller打包后的运行环境
    APP_DIR = Path(sys.executable).resolve().parent
    RESOURCE_DIR = Path(getattr(sys, '_MEIPASS', APP_DIR)).resolve()
else:
    # 开发环境
    APP_DIR = Path(__file__).resolve().parent.parent
    RESOURCE_DIR = APP_DIR

CONFIG_PATH = APP_DIR / 'config' / 'setting.yaml'
WEBUI_INDEX = RESOURCE_DIR / 'webui' / 'index.html'
ICON_PATH = APP_DIR / 'app.ico'
DEFAULT_SEVEN_ZIP_PATH = r'F:\soft\7-Zip\7z.exe'

# pywebview 常量兼容（新旧版本）
OPEN_DIALOG = getattr(webview, 'OPEN_DIALOG', None)
FOLDER_DIALOG = getattr(webview, 'FOLDER_DIALOG', None)
if OPEN_DIALOG is None and hasattr(webview, 'FileDialog'):
    OPEN_DIALOG = webview.FileDialog.OPEN
if FOLDER_DIALOG is None and hasattr(webview, 'FileDialog'):
    FOLDER_DIALOG = webview.FileDialog.FOLDER


# ============================================================================
# 配置管理函数
# ============================================================================
def load_config() -> dict:
    """
    加载配置文件。

    返回:
        dict: 配置字典
    """
    default_config = get_default_config()

    try:
        # 配置文件应该已由 ensure_config_exists() 创建
        if not CONFIG_PATH.exists():
            return default_config

        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}

        # 异常内容兜底
        if not isinstance(config, dict):
            return default_config

        # 补齐关键字段，避免旧配置缺项
        changed = False

        app_settings = config.get('app_settings')
        if not isinstance(app_settings, dict):
            app_settings = {}
            config['app_settings'] = app_settings
            changed = True

        if not app_settings.get('language'):
            app_settings['language'] = default_config['app_settings']['language']
            changed = True

        if not app_settings.get('seven_zip_path'):
            app_settings['seven_zip_path'] = default_config['app_settings']['seven_zip_path']
            changed = True

        if not isinstance(config.get('text_types'), list) or not config.get('text_types'):
            config['text_types'] = default_config['text_types']
            changed = True

        user_settings = config.get('user_settings')
        if not isinstance(user_settings, dict):
            config['user_settings'] = default_config['user_settings']
            changed = True
        else:
            if 'last_text_type' not in user_settings:
                user_settings['last_text_type'] = default_config['user_settings']['last_text_type']
                changed = True
            if 'auto_delete_source' not in user_settings:
                user_settings['auto_delete_source'] = default_config['user_settings']['auto_delete_source']
                changed = True

        if changed:
            save_config(config)

        return config
    except Exception as e:
        print(f"加载配置失败: {e}")
        return default_config


def save_config(config: dict):
    """
    保存配置文件
    
    参数:
        config: 配置字典
    """
    try:
        # 确保配置目录存在
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
    except Exception as e:
        raise RuntimeError(f"保存配置失败: {e}")


def get_default_config() -> dict:
    """
    获取默认配置
    
    返回:
        dict: 默认配置字典
    """
    return {
        "app_settings": {
            "language": "zh-CN",
            "seven_zip_path": DEFAULT_SEVEN_ZIP_PATH
        },
        "text_types": [
            {"label": "说明文本", "value": "说明文本"},
            {"label": "游戏简介", "value": "游戏简介"}
        ],
        "user_settings": {
            "last_text_type": "说明文本",
            "auto_delete_source": False
        }
    }


# ============================================================================
# AppApi 类 - 前端API接口
# ============================================================================
class AppApi:
    """
    前端API接口类
    
    所有方法返回dict，包含success字段表示操作是否成功。
    """
    
    def __init__(self):
        self.window = None
        self._global_drop_bound = False

    def _to_file_types(self, file_types):
        """
        兼容 pywebview 旧版/新版 file_types 参数格式。
        旧版常见: ('名称', '*.ext')
        新版常见: ('名称 (*.ext)',)
        """
        def normalize_pattern(pattern: str) -> str:
            parts = [p.strip() for p in pattern.split(';') if p.strip()]
            normalized_parts = []

            for part in parts:
                if '*' in part:
                    normalized_parts.append(part)
                    continue

                if part.startswith('.'):
                    normalized_parts.append(f'*{part}')
                    continue

                if '.' in part:
                    ext = part.split('.')[-1].strip()
                    normalized_parts.append(f'*.{ext}')
                    continue

                # 兜底：不合法模式则回退为全部文件，避免 pywebview parse_file_type 抛错
                return '*.*'

            return ';'.join(normalized_parts) if normalized_parts else '*.*'

        normalized = []
        for item in file_types:
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                name = str(item[0]).strip()
                pattern = normalize_pattern(str(item[1]).strip())
                normalized.append(f'{name} ({pattern})')
            else:
                normalized.append(str(item))
        return tuple(normalized)

    def _handle_native_drop(self, event: dict):
        """
        处理全局拖拽 drop 事件，将完整路径回传前端。
        """
        try:
            data_transfer = event.get('dataTransfer', {}) if isinstance(event, dict) else {}
            # 兼容某些文档里的字段名
            if not data_transfer and isinstance(event, dict):
                data_transfer = event.get('domTransfer', {})

            files = data_transfer.get('files', []) if isinstance(data_transfer, dict) else []
            paths = []

            for f in files:
                full_path = f.get('pywebviewFullPath') or f.get('path')
                if full_path:
                    paths.append(str(full_path))

            if not paths or self.window is None:
                return

            payload = json.dumps(paths, ensure_ascii=False)
            self.window.evaluate_js(f'window.handleNativeDrop({payload});')
        except Exception:
            # 拖拽辅助逻辑失败时不阻断主流程
            pass

    def get_initial_state(self, payload=None) -> dict:
        """
        返回初始状态

        返回:
            dict: {
                'success': bool,
                'data': {
                    'text_types': list[str],
                    'selected_text_type': str,
                    'source_files': list,
                    'archive_name': str,
                    'output_dir': str,
                    'seven_zip_path': str,
                    'seven_zip_valid': bool,
                    'disguise_types': list[dict],
                    'disguise_info': dict  # 每种类型的详细信息
                }
            }
        """
        try:
            config = load_config()
            app_settings = config.get('app_settings', {})
            user_settings = config.get('user_settings', {})
            text_types_config = config.get('text_types', [])

            # 提取文本类型列表
            text_types = [t.get('value', t.get('label', '')) for t in text_types_config]
            if not text_types:
                text_types = ['说明文本', '游戏简介']

            # 获取 7z 路径并验证
            seven_zip_path = app_settings.get('seven_zip_path', DEFAULT_SEVEN_ZIP_PATH)
            seven_zip_valid = Path(seven_zip_path).exists() if seven_zip_path else False

            # 构建伪装类型列表（基于 DISGUISE_TYPES 配置）
            disguise_types = [{'label': '不伪装', 'value': 'none'}]
            for type_key, type_info in DISGUISE_TYPES.items():
                disguise_types.append({
                    'label': type_info['label'],
                    'value': type_key
                })

            # 构建每种伪装类型的详细信息
            disguise_info = {}
            for type_key, type_info in DISGUISE_TYPES.items():
                has_custom = has_custom_template(type_key)
                disguise_info[type_key] = {
                    'label': type_info['label'],
                    'ext': type_info['ext'],
                    'can_generate': type_info['can_generate'],  # 是否可动态生成
                    'has_custom_template': has_custom,  # 是否有自定义模板
                    'is_available': type_info['can_generate'] or has_custom  # 是否可用
                }

            return {
                'success': True,
                'data': {
                    'text_types': text_types,
                    'selected_text_type': user_settings.get('last_text_type', '说明文本'),
                    'source_files': [],
                    'archive_name': '',
                    'output_dir': str(APP_DIR),
                    'seven_zip_path': seven_zip_path,
                    'seven_zip_valid': seven_zip_valid,
                    'disguise_types': disguise_types,
                    'disguise_info': disguise_info
                }
            }
        except Exception as e:
            return {
                'success': False,
                'data': None,
                'message': f'获取初始状态失败: {str(e)}'
            }
    
    def pick_files(self, payload=None) -> dict:
        """
        选择文件对话框，支持多选
        
        返回:
            dict: {'success': bool, 'data': {'files': list[str]}}
        """
        try:
            if self.window is None:
                return {'success': False, 'data': None, 'message': '窗口未初始化'}
            
            if OPEN_DIALOG is None:
                return {'success': False, 'data': None, 'message': '当前 pywebview 不支持文件选择对话框'}

            files = self.window.create_file_dialog(
                OPEN_DIALOG,
                allow_multiple=True,
                file_types=self._to_file_types((
                    ('所有文件', '*.*'),
                    ('压缩文件', '*.7z;*.zip;*.rar'),
                ))
            )
            
            if files:
                return {
                    'success': True,
                    'data': {'files': [str(f) for f in files]}
                }
            else:
                return {
                    'success': True,
                    'data': {'files': []}
                }
        except Exception as e:
            return {
                'success': False,
                'data': None,
                'message': f'选择文件失败: {str(e)}'
            }

    def pick_seven_zip_file(self, payload=None) -> dict:
        """
        选择 7z.exe 文件对话框。

        返回:
            dict: {'success': bool, 'data': {'path': str}}
        """
        try:
            if self.window is None:
                return {'success': False, 'data': None, 'message': '窗口未初始化'}
            if OPEN_DIALOG is None:
                return {'success': False, 'data': None, 'message': '当前 pywebview 不支持文件选择对话框'}

            files = self.window.create_file_dialog(
                OPEN_DIALOG,
                allow_multiple=False,
                file_types=self._to_file_types((
                    ('7z 可执行文件', '*.exe'),
                    ('可执行文件', '*.exe'),
                    ('所有文件', '*.*'),
                ))
            )

            if files:
                return {
                    'success': True,
                    'data': {'path': str(files[0])}
                }
            return {
                'success': True,
                'data': {'path': ''}
            }
        except Exception as e:
            return {
                'success': False,
                'data': None,
                'message': f'选择 7z 文件失败: {str(e)}'
            }
    
    def pick_folder(self, payload=None) -> dict:
        """
        选择文件夹对话框
        
        返回:
            dict: {'success': bool, 'data': {'folder': str}}
        """
        try:
            if self.window is None:
                return {'success': False, 'data': None, 'message': '窗口未初始化'}
            
            if FOLDER_DIALOG is None:
                return {'success': False, 'data': None, 'message': '当前 pywebview 不支持文件夹选择对话框'}

            folders = self.window.create_file_dialog(FOLDER_DIALOG)
            
            if folders:
                return {
                    'success': True,
                    'data': {'folder': str(folders[0])}
                }
            else:
                return {
                    'success': True,
                    'data': {'folder': ''}
                }
        except Exception as e:
            return {
                'success': False,
                'data': None,
                'message': f'选择文件夹失败: {str(e)}'
            }
    
    def pick_output_dir(self, payload=None) -> dict:
        """
        选择输出目录对话框
        
        返回:
            dict: {'success': bool, 'data': {'output_dir': str}}
        """
        try:
            if self.window is None:
                return {'success': False, 'data': None, 'message': '窗口未初始化'}
            
            if FOLDER_DIALOG is None:
                return {'success': False, 'data': None, 'message': '当前 pywebview 不支持文件夹选择对话框'}

            folders = self.window.create_file_dialog(FOLDER_DIALOG)
            
            if folders:
                return {
                    'success': True,
                    'data': {'output_dir': str(folders[0])}
                }
            else:
                return {
                    'success': True,
                    'data': {'output_dir': ''}
                }
        except Exception as e:
            return {
                'success': False,
                'data': None,
                'message': f'选择输出目录失败: {str(e)}'
            }
    
    def validate_seven_zip(self, payload=None) -> dict:
        """
        验证 setting.yaml 中配置的 7z.exe 是否存在。

        返回:
            dict: {'success': bool, 'data': {'exists': bool, 'path': str}}
        """
        try:
            config = load_config()
            app_settings = config.get('app_settings', {}) if isinstance(config, dict) else {}
            seven_zip_path = (app_settings.get('seven_zip_path') or DEFAULT_SEVEN_ZIP_PATH).strip()
            exists = Path(seven_zip_path).exists()

            return {
                'success': True,
                'data': {
                    'exists': exists,
                    'path': seven_zip_path
                }
            }
        except Exception as e:
            return {
                'success': False,
                'data': None,
                'message': f'验证7z路径失败: {str(e)}'
            }

    def update_seven_zip_path(self, payload: dict) -> dict:
        """
        更新7z路径配置（写入 setting.yaml）。

        参数:
            payload: {'path': str}

        返回:
            dict: {'success': bool, 'message': str}
        """
        try:
            if not payload or 'path' not in payload:
                return {
                    'success': False,
                    'message': '路径参数缺失'
                }

            new_path = str(payload['path']).strip()

            # 验证路径
            if not Path(new_path).exists():
                return {
                    'success': False,
                    'message': f'路径不存在: {new_path}'
                }

            # 检查是否是7z.exe
            if not new_path.lower().endswith('7z.exe'):
                return {
                    'success': False,
                    'message': '请选择有效的7z.exe文件'
                }

            config = load_config()
            if 'app_settings' not in config or not isinstance(config['app_settings'], dict):
                config['app_settings'] = {}

            config['app_settings']['seven_zip_path'] = new_path
            save_config(config)

            return {
                'success': True,
                'message': '7z路径更新成功'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'更新7z路径失败: {str(e)}'
            }

    def reveal_output_file(self, payload: dict = None) -> dict:
        """
        在资源管理器中定位输出文件。

        参数:
            payload: {'zip_path': str}

        返回:
            dict: {'success': bool, 'message': str}
        """
        try:
            if not payload or 'zip_path' not in payload:
                return {
                    'success': False,
                    'message': '输出文件路径缺失'
                }

            zip_path = str(payload.get('zip_path') or '').strip()
            if not zip_path:
                return {
                    'success': False,
                    'message': '输出文件路径为空'
                }

            target = Path(zip_path).resolve()
            parent = target.parent

            if sys.platform.startswith('win'):
                creationflags = subprocess.CREATE_NO_WINDOW

                if target.exists() and target.is_file():
                    subprocess.Popen(
                        ['explorer', f'/select,{str(target)}'],
                        creationflags=creationflags
                    )
                    return {
                        'success': True,
                        'message': '已打开输出文件位置'
                    }

                if parent.exists() and parent.is_dir():
                    subprocess.Popen(
                        ['explorer', str(parent)],
                        creationflags=creationflags
                    )
                    return {
                        'success': True,
                        'message': '已打开输出目录'
                    }
            else:
                if target.exists() and target.is_file() and parent.exists():
                    subprocess.Popen(['xdg-open', str(parent)])
                    return {
                        'success': True,
                        'message': '已打开输出目录'
                    }

                if parent.exists() and parent.is_dir():
                    subprocess.Popen(['xdg-open', str(parent)])
                    return {
                        'success': True,
                        'message': '已打开输出目录'
                    }

            return {
                'success': False,
                'message': f'路径不存在: {zip_path}'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'打开输出位置失败: {str(e)}'
            }
    
    def start_packaging(self, payload: dict) -> dict:
        """
        开始打包

        参数:
            payload: {
                'source_files': list[str],
                'archive_name': str,
                'text_type': str,
                'text_content': str,
                'output_dir': str,
                'disguise_type': str,  # 可选: none/png/jpg/mp3/mp4/pdf
                'carrier_path': str  # 可选: 自定义载体文件路径
            }

        返回:
            dict: {
                'success': bool,
                'message': str,
                'data': {
                    'password': str,
                    'zip_path': str,
                    'disguise_path': str
                }
            }
        """
        try:
            # 验证参数
            if not payload:
                return {
                    'success': False,
                    'message': '参数不能为空',
                    'data': None
                }

            source_files = payload.get('source_files', [])
            archive_name = payload.get('archive_name', '')
            text_type = payload.get('text_type', '说明文本')
            text_content = payload.get('text_content', '')
            output_dir = payload.get('output_dir', str(APP_DIR))
            disguise_type = payload.get('disguise_type', 'none')
            carrier_path = payload.get('carrier_path')  # 可为空

            if not source_files:
                return {
                    'success': False,
                    'message': '请选择要打包的文件',
                    'data': None
                }

            if not archive_name:
                return {
                    'success': False,
                    'message': '请输入压缩包名称',
                    'data': None
                }

            # 调用核心打包函数（含伪装）
            result = process_packaging_with_disguise(
                source_paths=source_files,
                output_dir=output_dir,
                archive_name=archive_name,
                text_type=text_type,
                text_content=text_content,
                disguise_type=disguise_type,
                carrier_path=carrier_path
            )

            return {
                'success': result.get('success', False),
                'message': result.get('message', ''),
                'data': {
                    'password': result.get('password', ''),
                    'zip_path': result.get('zip_path', ''),
                    'disguise_path': result.get('disguise_path', '')
                }
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'打包过程异常: {str(e)}',
                'data': None
            }
    
    def confirm_delete(self, payload: dict) -> dict:
        """
        确认删除源文件
        
        参数:
            payload: {'files': list[str]}
        
        返回:
            dict: {
                'success': bool,
                'message': str,
                'data': {'deleted': list[str]}
            }
        """
        try:
            if not payload:
                return {
                    'success': False,
                    'message': '参数不能为空',
                    'data': {'deleted': []}
                }
            
            files = payload.get('files', [])
            
            if not files:
                return {
                    'success': False,
                    'message': '没有要删除的文件',
                    'data': {'deleted': []}
                }
            
            # 调用核心删除函数
            result = delete_source_files(files)
            
            return {
                'success': result.get('success', False),
                'message': result.get('message', ''),
                'data': {
                    'deleted': result.get('deleted', [])
                }
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'删除过程异常: {str(e)}',
                'data': {'deleted': []}
            }
    
    def save_settings(self, payload: dict) -> dict:
        """
        保存用户设置

        参数:
            payload: 用户设置字典

        返回:
            dict: {'success': bool, 'message': str}
        """
        try:
            if not payload:
                return {
                    'success': False,
                    'message': '设置内容为空'
                }

            # 加载现有配置
            config = load_config()

            # 更新用户设置
            if 'user_settings' not in config:
                config['user_settings'] = {}

            config['user_settings'].update(payload)

            # 保存配置
            save_config(config)

            return {
                'success': True,
                'message': '设置保存成功'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'保存设置失败: {str(e)}'
            }

    def save_text_types(self, payload: dict) -> dict:
        """
        保存文本类型列表

        参数:
            payload: {'text_types': list[str]}

        返回:
            dict: {'success': bool, 'message': str}
        """
        try:
            if not payload or 'text_types' not in payload:
                return {
                    'success': False,
                    'message': '文本类型列表为空'
                }

            text_types = payload.get('text_types', [])
            if not isinstance(text_types, list) or len(text_types) == 0:
                return {
                    'success': False,
                    'message': '文本类型列表无效'
                }

            # 加载现有配置
            config = load_config()

            # 更新文本类型列表
            config['text_types'] = [
                {'label': t, 'value': t} for t in text_types
            ]

            # 保存配置
            save_config(config)

            return {
                'success': True,
                'message': '文本类型保存成功'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'保存文本类型失败: {str(e)}'
            }

    def pick_carrier_file(self, payload: dict) -> dict:
        """
        选择载体文件对话框

        参数:
            payload: {'media_type': str}  # png/jpg/mp3/mp4/pdf

        返回:
            dict: {'success': bool, 'data': {'path': str}}
        """
        try:
            if self.window is None:
                return {'success': False, 'data': None, 'message': '窗口未初始化'}

            media_type = payload.get('media_type', 'png') if payload else 'png'

            # 根据类型设置文件过滤器
            type_filters = {
                'png': ('PNG图片', '*.png'),
                'jpg': ('JPG图片', '*.jpg;*.jpeg'),
                'mp3': ('MP3音频', '*.mp3'),
                'mp4': ('MP4视频', '*.mp4'),
                'pdf': ('PDF文档', '*.pdf'),
                'exe': ('可执行文件', '*.exe'),
            }

            filter_name, filter_pattern = type_filters.get(media_type, ('所有文件', '*.*'))

            if OPEN_DIALOG is None:
                return {'success': False, 'data': None, 'message': '当前 pywebview 不支持文件选择对话框'}

            files = self.window.create_file_dialog(
                OPEN_DIALOG,
                allow_multiple=False,
                file_types=self._to_file_types(((filter_name, filter_pattern),))
            )

            if files:
                return {
                    'success': True,
                    'data': {'path': str(files[0])}
                }
            else:
                return {
                    'success': True,
                    'data': {'path': ''}
                }
        except Exception as e:
            return {
                'success': False,
                'data': None,
                'message': f'选择载体文件失败: {str(e)}'
            }

    def get_disguise_template_status(self, payload=None) -> dict:
        """
        获取伪装模板状态

        返回:
            dict: {
                'success': bool,
                'data': {
                    'templates': dict[str, {
                        'has_custom': bool,
                        'can_generate': bool,
                        'is_available': bool,
                        'custom_path': str
                    }]
                }
            }
        """
        try:
            templates = {}
            for type_key, type_info in DISGUISE_TYPES.items():
                has_custom = has_custom_template(type_key)
                custom_path = str(get_default_template_path(type_key)) if has_custom else ''
                templates[type_key] = {
                    'has_custom': has_custom,
                    'can_generate': type_info['can_generate'],
                    'is_available': type_info['can_generate'] or has_custom,
                    'custom_path': custom_path
                }

            return {
                'success': True,
                'data': {'templates': templates}
            }
        except Exception as e:
            return {
                'success': False,
                'data': None,
                'message': f'获取模板状态失败: {str(e)}'
            }

    def set_disguise_template(self, payload: dict) -> dict:
        """
        设置伪装默认模板

        参数:
            payload: {'media_type': str, 'source_path': str}

        返回:
            dict: {'success': bool, 'message': str}
        """
        try:
            if not payload:
                return {'success': False, 'message': '参数不能为空'}

            media_type = payload.get('media_type')
            source_path = payload.get('source_path')

            if not media_type or not source_path:
                return {'success': False, 'message': '缺少必要参数'}

            result = set_default_template(media_type, source_path)
            return result
        except Exception as e:
            return {'success': False, 'message': f'设置模板失败: {str(e)}'}

    def remove_disguise_template(self, payload: dict) -> dict:
        """
        移除伪装默认模板（恢复动态生成）

        参数:
            payload: {'media_type': str}

        返回:
            dict: {'success': bool, 'message': str}
        """
        try:
            if not payload:
                return {'success': False, 'message': '参数不能为空'}

            media_type = payload.get('media_type')
            if not media_type:
                return {'success': False, 'message': '缺少媒体类型参数'}

            result = remove_default_template(media_type)
            return result
        except Exception as e:
            return {'success': False, 'message': f'移除模板失败: {str(e)}'}


# ============================================================================
# 主函数入口
# ============================================================================
def ensure_config_exists():
    """
    确保配置文件存在，避免首次启动时阻塞。
    """
    try:
        if not CONFIG_PATH.exists():
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            default_config = get_default_config()
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                yaml.dump(default_config, f, allow_unicode=True, default_flow_style=False)
    except Exception as e:
        print(f"初始化配置文件失败: {e}")


def main():
    """
    主函数入口

    创建pywebview窗口并启动应用。
    """
    # 预先确保配置文件存在，避免首次启动阻塞 UI
    ensure_config_exists()

    api = AppApi()

    window = webview.create_window(
        '自动打包器',
        url=str(WEBUI_INDEX),
        js_api=api,
        width=900,
        height=695,
        min_size=(800, 695),
        text_select=True,
    )

    api.window = window

    def on_loaded():
        if api._global_drop_bound:
            return

        try:
            doc = window.dom.document
            if doc:
                doc.on('drop', DOMEventHandler(api._handle_native_drop, prevent_default=True))
                api._global_drop_bound = True
        except Exception:
            # 前端仍有 JS 兜底
            pass

    window.events.loaded += on_loaded

    # 启动 webview
    # 采用 document 级 drop 监听，支持整个窗口拖拽并保留完整文件路径。
    # Windows 下通过 start(icon=...) 指定左上角窗口图标。
    icon_arg = str(ICON_PATH) if ICON_PATH.exists() else None
    webview.start(debug=False, http_server=False, icon=icon_arg)


if __name__ == '__main__':
    main()
