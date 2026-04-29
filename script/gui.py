"""
自动打包器 GUI入口和API桥接模块

提供pywebview API接口，连接前端UI和后端核心逻辑。
"""

import json
import sys
import webview
from pathlib import Path
import yaml
from webview.dom import DOMEventHandler

from core import (
    generate_password,
    process_packaging,
    delete_source_files
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
DEFAULT_SEVEN_ZIP_PATH = r'C:\Program Files\7-Zip\7z.exe'


# ============================================================================
# 配置管理函数
# ============================================================================
def load_config() -> dict:
    """
    加载配置文件；若不存在则自动创建默认配置文件。

    返回:
        dict: 配置字典
    """
    default_config = get_default_config()

    try:
        # 缺失时自动创建默认配置
        if not CONFIG_PATH.exists():
            save_config(default_config)
            return default_config

        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}

        # 异常内容兜底
        if not isinstance(config, dict):
            save_config(default_config)
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
        try:
            save_config(default_config)
        except Exception:
            pass
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
        self._drop_bound = False

    def _handle_native_drop(self, event: dict):
        """
        处理 pywebview 原生 drop 事件，并将完整路径回传给前端。
        """
        try:
            files = event.get('dataTransfer', {}).get('files', [])
            paths = []
            for f in files:
                full_path = f.get('pywebviewFullPath') or f.get('path')
                if full_path:
                    paths.append(str(full_path))

            if paths:
                payload = json.dumps(paths, ensure_ascii=False)
                # 调用前端函数，避免浏览器层无法拿到本地路径
                self.window.evaluate_js(f'window.handleNativeDrop({payload});')
        except Exception as e:
            print(f'处理拖拽事件失败: {e}')
    
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
                    'seven_zip_path': str
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
            
            return {
                'success': True,
                'data': {
                    'text_types': text_types,
                    'selected_text_type': user_settings.get('last_text_type', '说明文本'),
                    'source_files': [],
                    'archive_name': '',
                    'output_dir': str(APP_DIR),
                    'seven_zip_path': app_settings.get('seven_zip_path', r'C:\Program Files\7-Zip\7z.exe')
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
            
            files = self.window.create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=True,
                file_types=('所有文件 (*.*)', '压缩文件 (*.7z;*.zip;*.rar)')
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
    
    def pick_folder(self, payload=None) -> dict:
        """
        选择文件夹对话框
        
        返回:
            dict: {'success': bool, 'data': {'folder': str}}
        """
        try:
            if self.window is None:
                return {'success': False, 'data': None, 'message': '窗口未初始化'}
            
            folders = self.window.create_file_dialog(webview.FOLDER_DIALOG)
            
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
            
            folders = self.window.create_file_dialog(webview.FOLDER_DIALOG)
            
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
    
    def start_packaging(self, payload: dict) -> dict:
        """
        开始打包
        
        参数:
            payload: {
                'source_files': list[str],
                'archive_name': str,
                'text_type': str,
                'text_content': str,
                'output_dir': str
            }
        
        返回:
            dict: {
                'success': bool,
                'message': str,
                'data': {
                    'password': str,
                    'zip_path': str
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
            
            # 调用核心打包函数
            result = process_packaging(
                source_paths=source_files,
                output_dir=output_dir,
                archive_name=archive_name,
                text_type=text_type,
                text_content=text_content
            )
            
            return {
                'success': result.get('success', False),
                'message': result.get('message', ''),
                'data': {
                    'password': result.get('password', ''),
                    'zip_path': result.get('zip_path', '')
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


# ============================================================================
# 主函数入口
# ============================================================================
def main():
    """
    主函数入口
    
    创建pywebview窗口并启动应用。
    """
    api = AppApi()
    
    window = webview.create_window(
        '自动打包器',
        url=str(WEBUI_INDEX),
        js_api=api,
        width=900,
        height=650,
        min_size=(800, 600),
        text_select=True,
    )
    
    api.window = window
    
    def on_loaded():
        # 绑定 drop 事件（仅绑定一次）
        if not api._drop_bound:
            try:
                drop_zone = window.dom.get_element('#dropZone')
                if drop_zone:
                    drop_zone.on(
                        'drop',
                        DOMEventHandler(api._handle_native_drop, prevent_default=True)
                    )
                    api._drop_bound = True
            except Exception as e:
                print(f'绑定拖拽事件失败: {e}')

    window.events.loaded += on_loaded

    # 启动webview（debug=False用于生产环境）
    webview.start(debug=False)


if __name__ == '__main__':
    main()
