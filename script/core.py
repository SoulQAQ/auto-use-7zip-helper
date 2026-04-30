"""
自动打包器核心业务逻辑模块

提供文件打包、密码生成、压缩等核心功能。
"""

import os
import random
import shutil
import string
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import yaml

DEFAULT_SEVEN_ZIP_PATH = r"C:\Program Files\7-Zip\7z.exe"


def run_seven_zip_command(cmd: list[str]) -> subprocess.CompletedProcess:
    """
    运行 7z 命令并在 Windows 下隐藏控制台窗口。
    """
    run_kwargs = {
        'capture_output': True,
        'text': True,
        'encoding': 'utf-8',
        'errors': 'replace'
    }

    if os.name == 'nt':
        run_kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

    return subprocess.run(cmd, **run_kwargs)


def load_config() -> dict:
    """
    加载配置文件；若缺失则自动创建默认 setting.yaml。

    返回:
        dict: 配置字典
    """
    if getattr(__import__('sys'), 'frozen', False):
        app_dir = Path(__import__('sys').executable).resolve().parent
    else:
        app_dir = Path(__file__).resolve().parent.parent

    config_path = app_dir / "config" / "setting.yaml"
    default_config = {
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

    try:
        if not config_path.exists():
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(default_config, f, allow_unicode=True, default_flow_style=False)
            return default_config

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        if not isinstance(config, dict):
            raise ValueError("配置文件格式无效")

        # 补齐关键字段，兼容旧配置
        changed = False
        app_settings = config.get("app_settings")
        if not isinstance(app_settings, dict):
            app_settings = {}
            config["app_settings"] = app_settings
            changed = True

        if not app_settings.get("language"):
            app_settings["language"] = "zh-CN"
            changed = True

        if not app_settings.get("seven_zip_path"):
            app_settings["seven_zip_path"] = DEFAULT_SEVEN_ZIP_PATH
            changed = True

        if changed:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

        return config
    except Exception:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(default_config, f, allow_unicode=True, default_flow_style=False)
        return default_config


def generate_password(length: int = 10) -> str:
    """
    生成A-Za-z0-9的随机密码
    
    参数:
        length: 密码长度，默认10位
        
    返回:
        str: 生成的随机密码
    """
    characters = string.ascii_letters + string.digits  # A-Za-z0-9
    return ''.join(random.choice(characters) for _ in range(length))


def compress_to_7z(
    source_paths: list[str],
    output_path: str,
    password: str
) -> dict:
    """
    使用7zip加密压缩
    
    参数:
        source_paths: 源文件/文件夹路径列表
        output_path: 输出7z文件路径
        password: 加密密码
        
    返回:
        dict: {'success': bool, 'message': str}
    """
    try:
        # 仅从 setting.yaml 读取 7z 路径
        config = load_config()
        seven_zip_path = config.get("app_settings", {}).get(
            "seven_zip_path",
            DEFAULT_SEVEN_ZIP_PATH
        )
        
        # 检查7z是否存在
        if not Path(seven_zip_path).exists():
            return {
                'success': False,
                'message': f'7-Zip未找到，请检查路径: {seven_zip_path}'
            }
        
        # 验证源路径
        valid_sources = []
        for src in source_paths:
            if Path(src).exists():
                valid_sources.append(src)
            else:
                return {
                    'success': False,
                    'message': f'源路径不存在: {src}'
                }
        
        if not valid_sources:
            return {
                'success': False,
                'message': '没有有效的源路径'
            }
        
        # 确保输出目录存在
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 构建命令
        # 格式: 7z a -t7z -p{password} -mhe=on "{output}" {sources}
        cmd = [
            seven_zip_path,
            'a',  # 添加到压缩包
            '-t7z',  # 7z格式
            f'-p{password}',  # 密码
            '-mhe=on',  # 启用文件名加密
            output_path
        ] + valid_sources
        
        # 执行命令
        result = run_seven_zip_command(cmd)
        
        if result.returncode == 0:
            return {
                'success': True,
                'message': f'7z压缩成功: {output_path}'
            }
        else:
            error_msg = result.stderr or result.stdout or '未知错误'
            return {
                'success': False,
                'message': f'7z压缩失败: {error_msg}'
            }
            
    except Exception as e:
        return {
            'success': False,
            'message': f'7z压缩异常: {str(e)}'
        }


def create_password_file(output_dir: str, password: str) -> str:
    """
    创建空文件，文件名为【解压：{password}】
    
    参数:
        output_dir: 输出目录
        password: 密码
        
    返回:
        str: 文件完整路径
    """
    try:
        # 确保目录存在
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 创建文件名（使用全角冒号）
        filename = f"解压：{password}.txt"
        file_path = output_path / filename
        
        # 创建空文件
        file_path.touch()
        
        return str(file_path)
        
    except Exception as e:
        raise RuntimeError(f'创建密码文件失败: {str(e)}')


def create_text_file(output_dir: str, text_type: str, content: str = '') -> str:
    """
    创建txt文件，文件名为text_type
    
    参数:
        output_dir: 输出目录
        text_type: 文本类型（如"说明文本"或"游戏简介"）
        content: 文件内容，默认为空
        
    返回:
        str: 文件完整路径
    """
    try:
        # 确保目录存在
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 创建文件
        filename = f"{text_type}.txt"
        file_path = output_path / filename
        
        # 写入内容（如果提供）
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return str(file_path)
        
    except Exception as e:
        raise RuntimeError(f'创建文本文件失败: {str(e)}')


def compress_to_zip(
    source_paths: list[str],
    output_path: str
) -> dict:
    """
    使用7zip以存储模式打包成zip
    
    参数:
        source_paths: 要打包的文件列表（7z文件、密码文件、txt文件）
        output_path: 输出zip文件路径
        
    返回:
        dict: {'success': bool, 'message': str}
    """
    try:
        # 仅从 setting.yaml 读取 7z 路径
        config = load_config()
        seven_zip_path = config.get("app_settings", {}).get(
            "seven_zip_path",
            DEFAULT_SEVEN_ZIP_PATH
        )
        
        # 检查7z是否存在
        if not Path(seven_zip_path).exists():
            return {
                'success': False,
                'message': f'7-Zip未找到，请检查路径: {seven_zip_path}'
            }
        
        # 验证源路径
        valid_sources = []
        for src in source_paths:
            if Path(src).exists():
                valid_sources.append(src)
            else:
                return {
                    'success': False,
                    'message': f'源文件不存在: {src}'
                }
        
        if not valid_sources:
            return {
                'success': False,
                'message': '没有有效的源文件'
            }
        
        # 确保输出目录存在
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 构建命令
        # 格式: 7z a -tzip -mx=0 "{output}" {sources}
        # mx=0 表示存储模式（无压缩）
        cmd = [
            seven_zip_path,
            'a',  # 添加到压缩包
            '-tzip',  # zip格式
            '-mx=0',  # 存储模式（无压缩）
            output_path
        ] + valid_sources
        
        # 执行命令
        result = run_seven_zip_command(cmd)
        
        if result.returncode == 0:
            return {
                'success': True,
                'message': f'ZIP打包成功: {output_path}'
            }
        else:
            error_msg = result.stderr or result.stdout or '未知错误'
            return {
                'success': False,
                'message': f'ZIP打包失败: {error_msg}'
            }
            
    except Exception as e:
        return {
            'success': False,
            'message': f'ZIP打包异常: {str(e)}'
        }


def process_packaging(
    source_paths: list[str],
    output_dir: str,
    archive_name: str,
    text_type: str,
    text_content: str = ''
) -> dict:
    """
    执行完整打包流程:
    1. 生成随机密码
    2. 打包成加密7z
    3. 创建密码文件
    4. 创建说明文本文件
    5. 打包成存储模式zip
    6. 清理临时文件
    
    参数:
        source_paths: 源文件列表
        output_dir: 输出目录
        archive_name: 压缩包名称（不含扩展名）
        text_type: 文本类型
        text_content: 文本内容
        
    返回:
        dict: {
            'success': bool,
            'message': str,
            'password': str,
            'seven_z_path': str,
            'zip_path': str
        }
    """
    temp_dir = None
    
    try:
        # 1. 验证输入
        if not source_paths:
            return {
                'success': False,
                'message': '源文件列表为空',
                'password': '',
                'seven_z_path': '',
                'zip_path': ''
            }
        
        # 验证源路径存在
        for src in source_paths:
            if not Path(src).exists():
                return {
                    'success': False,
                    'message': f'源路径不存在: {src}',
                    'password': '',
                    'seven_z_path': '',
                    'zip_path': ''
                }
        
        # 创建临时工作目录
        temp_dir = Path(tempfile.mkdtemp(prefix=f"packaging_{archive_name}_"))
        
        # 确保输出目录存在
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 2. 生成随机密码
        password = generate_password(10)
        
        # 3. 打包成加密7z
        seven_z_path = temp_dir / f"{archive_name}.7z"
        result = compress_to_7z(
            source_paths=source_paths,
            output_path=str(seven_z_path),
            password=password
        )
        
        if not result['success']:
            return {
                'success': False,
                'message': result['message'],
                'password': password,
                'seven_z_path': '',
                'zip_path': ''
            }
        
        # 4. 创建密码文件
        try:
            password_file_path = create_password_file(str(temp_dir), password)
        except Exception as e:
            return {
                'success': False,
                'message': str(e),
                'password': password,
                'seven_z_path': str(seven_z_path),
                'zip_path': ''
            }
        
        # 5. 创建说明文本文件（仅当内容非空时）
        text_file_path = None
        if text_content and text_content.strip():
            try:
                text_file_path = create_text_file(str(temp_dir), text_type, text_content)
            except Exception as e:
                return {
                    'success': False,
                    'message': str(e),
                    'password': password,
                    'seven_z_path': str(seven_z_path),
                    'zip_path': ''
                }

        # 6. 打包成存储模式zip
        zip_path = output_path / f"{archive_name}.zip"

        # 构建要打包的文件列表
        files_to_zip = [str(seven_z_path), password_file_path]
        if text_file_path:
            files_to_zip.append(text_file_path)

        result = compress_to_zip(
            source_paths=files_to_zip,
            output_path=str(zip_path)
        )
        
        if not result['success']:
            return {
                'success': False,
                'message': result['message'],
                'password': password,
                'seven_z_path': str(seven_z_path),
                'zip_path': ''
            }
        
        return {
            'success': True,
            'message': f'打包成功: {zip_path}',
            'password': password,
            'seven_z_path': str(seven_z_path),
            'zip_path': str(zip_path)
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': f'打包过程异常: {str(e)}',
            'password': '',
            'seven_z_path': '',
            'zip_path': ''
        }
    finally:
        # 7. 清理临时文件
        if temp_dir and Path(temp_dir).exists():
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass  # 忽略清理失败


def delete_source_files(paths: list[str]) -> dict:
    """
    删除源文件/文件夹
    
    参数:
        paths: 要删除的路径列表
        
    返回:
        dict: {'success': bool, 'message': str, 'deleted': list[str]}
    """
    deleted = []
    errors = []
    
    try:
        for path_str in paths:
            path = Path(path_str)
            
            if not path.exists():
                errors.append(f'路径不存在: {path_str}')
                continue
            
            try:
                if path.is_file():
                    path.unlink()
                    deleted.append(path_str)
                elif path.is_dir():
                    shutil.rmtree(path)
                    deleted.append(path_str)
                else:
                    errors.append(f'不支持的路径类型: {path_str}')
            except PermissionError:
                errors.append(f'权限不足，无法删除: {path_str}')
            except Exception as e:
                errors.append(f'删除失败 {path_str}: {str(e)}')
        
        if errors:
            return {
                'success': len(deleted) > 0,  # 部分成功也算成功
                'message': f'完成删除，但有错误: {"; ".join(errors)}',
                'deleted': deleted
            }
        else:
            return {
                'success': True,
                'message': f'成功删除 {len(deleted)} 个项目',
                'deleted': deleted
            }
            
    except Exception as e:
        return {
            'success': False,
            'message': f'删除过程异常: {str(e)}',
            'deleted': deleted
        }


# 测试代码
if __name__ == "__main__":
    # 测试密码生成
    print("测试密码生成:")
    for i in range(5):
        print(f"  密码 {i+1}: {generate_password(10)}")
    
    # 测试配置加载
    print("\n测试配置加载:")
    config = load_config()
    print(f"  配置: {config}")
    
    print("\n核心模块加载成功!")
