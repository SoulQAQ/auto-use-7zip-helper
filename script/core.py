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

DEFAULT_SEVEN_ZIP_PATH = r"F:\soft\7-Zip\7z.exe"


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


# ============================================================================
# 媒体伪装功能
# ============================================================================

# 支持的伪装类型配置
DISGUISE_TYPES = {
    'png': {'label': '伪装为图片 PNG', 'ext': '.png', 'can_generate': True},
    'jpg': {'label': '伪装为图片 JPG', 'ext': '.jpg', 'can_generate': False},
    'mp3': {'label': '伪装为音频 MP3', 'ext': '.mp3', 'can_generate': False},
    'mp4': {'label': '伪装为视频 MP4', 'ext': '.mp4', 'can_generate': False},
    'pdf': {'label': '伪装为文档 PDF', 'ext': '.pdf', 'can_generate': True},
}


def get_media_template_path() -> Path:
    """获取媒体模板目录路径"""
    if getattr(__import__('sys'), 'frozen', False):
        app_dir = Path(__import__('sys').executable).resolve().parent
        resource_dir = Path(getattr(__import__('sys'), '_MEIPASS', app_dir)).resolve()
    else:
        resource_dir = Path(__file__).resolve().parent.parent
    return resource_dir / 'media-templates'


def generate_random_png() -> bytes:
    """
    生成一个随机颜色/大小的PNG图片数据（每次都不同）

    返回:
        bytes: PNG文件二进制数据
    """
    import zlib

    # 随机尺寸 (50-200)
    width = random.randint(50, 200)
    height = random.randint(50, 200)

    # 随机颜色
    r = random.randint(0, 255)
    g = random.randint(0, 255)
    b = random.randint(0, 255)

    def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
        chunk = chunk_type + data
        crc = zlib.crc32(chunk) & 0xffffffff
        return len(data).to_bytes(4, 'big') + chunk + crc.to_bytes(4, 'big')

    # PNG签名
    signature = b'\x89PNG\r\n\x1a\n'

    # IHDR chunk
    ihdr_data = (
        width.to_bytes(4, 'big') +
        height.to_bytes(4, 'big') +
        b'\x08\x02\x00\x00\x00'
    )
    ihdr = png_chunk(b'IHDR', ihdr_data)

    # IDAT chunk (图像数据) - 添加随机纹理
    raw_data = b''
    for y in range(height):
        raw_data += b'\x00'  # 过滤器类型
        for x in range(width):
            # 添加一些随机变化，不是纯色
            noise = random.randint(-20, 20)
            raw_data += bytes([
                max(0, min(255, r + noise)),
                max(0, min(255, g + noise)),
                max(0, min(255, b + noise))
            ])

    compressed = zlib.compress(raw_data, 9)
    idat = png_chunk(b'IDAT', compressed)

    # IEND chunk
    iend = png_chunk(b'IEND', b'')

    return signature + ihdr + idat + iend


def generate_random_pdf() -> bytes:
    """
    生成一个随机内容的PDF文件数据（每次都不同）

    返回:
        bytes: PDF文件二进制数据
    """
    # 随机纸张尺寸
    width = random.randint(200, 600)
    height = random.randint(300, 800)

    # 随机创建时间戳
    import time
    timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime())

    content = f"""%PDF-1.4
%âãÏÓ
1 0 obj
<< /Type /Catalog /Pages 2 0 R /Producer (AutoPacker) /CreationDate (D:{timestamp}) >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT /F1 12 Tf 100 {height-100} Td () Tj ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f
0000000015 00000 n
0000000128 00000 n
0000000191 00000 n
0000000342 00000 n
0000000436 00000 n
trailer
<< /Size 6 /Root 1 0 R >>
startxref
520
%%EOF"""
    return content.encode('utf-8')


def get_default_template_path(media_type: str) -> Path:
    """获取默认模板文件路径"""
    template_dir = get_media_template_path()
    ext_map = {'png': '.png', 'jpg': '.jpg', 'mp3': '.mp3', 'mp4': '.mp4', 'pdf': '.pdf'}
    return template_dir / f"default{ext_map.get(media_type, '.bin')}"


def has_custom_template(media_type: str) -> bool:
    """检查是否有自定义默认模板"""
    template_path = get_default_template_path(media_type)
    return template_path.exists()


def set_default_template(media_type: str, source_path: str) -> dict:
    """
    设置默认模板文件

    参数:
        media_type: 媒体类型
        source_path: 源文件路径

    返回:
        dict: {'success': bool, 'message': str}
    """
    try:
        if media_type not in DISGUISE_TYPES:
            return {'success': False, 'message': f'不支持的媒体类型: {media_type}'}

        source = Path(source_path)
        if not source.exists():
            return {'success': False, 'message': f'源文件不存在: {source_path}'}

        # 确保模板目录存在
        template_dir = get_media_template_path()
        template_dir.mkdir(parents=True, exist_ok=True)

        # 复制文件
        dest_path = get_default_template_path(media_type)
        shutil.copy2(source, dest_path)

        return {'success': True, 'message': f'已设置 {media_type.upper()} 默认模板'}
    except Exception as e:
        return {'success': False, 'message': f'设置模板失败: {str(e)}'}


def remove_default_template(media_type: str) -> dict:
    """
    移除默认模板文件（恢复使用动态生成）

    参数:
        media_type: 媒体类型

    返回:
        dict: {'success': bool, 'message': str}
    """
    try:
        if media_type not in DISGUISE_TYPES:
            return {'success': False, 'message': f'不支持的媒体类型: {media_type}'}

        template_path = get_default_template_path(media_type)
        if template_path.exists():
            template_path.unlink()
            return {'success': True, 'message': f'已移除 {media_type.upper()} 默认模板，将使用动态生成'}
        else:
            return {'success': True, 'message': f'{media_type.upper()} 当前使用动态生成'}
    except Exception as e:
        return {'success': False, 'message': f'移除模板失败: {str(e)}'}


def get_disguise_carrier(media_type: str, custom_path: str = None) -> bytes:
    """
    获取伪装载体数据

    优先级:
    1. 自定义载体文件 (custom_path)
    2. 用户设置的默认模板
    3. 动态生成随机内容

    参数:
        media_type: 媒体类型 (png/jpg/mp3/mp4/pdf)
        custom_path: 自定义载体文件路径（可选）

    返回:
        bytes: 媒体文件二进制数据
    """
    # 1. 优先使用自定义载体
    if custom_path:
        custom = Path(custom_path)
        if custom.exists():
            with open(custom, 'rb') as f:
                return f.read()

    # 2. 检查用户设置的默认模板
    default_template = get_default_template_path(media_type)
    if default_template.exists():
        with open(default_template, 'rb') as f:
            return f.read()

    # 3. 动态生成
    if media_type == 'png':
        return generate_random_png()
    elif media_type == 'pdf':
        return generate_random_pdf()
    else:
        # jpg/mp3/mp4 没有模板也没有生成能力
        raise FileNotFoundError(
            f'没有可用的 {media_type.upper()} 载体。'
            f'请选择一个载体文件或在设置中配置默认模板。'
        )


def disguise_as_media(
    zip_path: str,
    output_dir: str,
    archive_name: str,
    media_type: str,
    carrier_path: str = None
) -> dict:
    """
    将ZIP文件伪装成媒体文件

    参数:
        zip_path: ZIP文件路径
        output_dir: 输出目录
        archive_name: 输出文件名（不含扩展名）
        media_type: 媒体类型 (png/jpg/mp3/mp4/pdf)
        carrier_path: 自定义载体文件路径（可选）

    返回:
        dict: {'success': bool, 'message': str, 'output_path': str}
    """
    try:
        if media_type not in DISGUISE_TYPES:
            return {'success': False, 'message': f'不支持的媒体类型: {media_type}', 'output_path': ''}

        # 验证ZIP文件存在
        if not Path(zip_path).exists():
            return {'success': False, 'message': f'ZIP文件不存在: {zip_path}', 'output_path': ''}

        # 获取伪装载体
        try:
            carrier_data = get_disguise_carrier(media_type, carrier_path)
        except FileNotFoundError as e:
            return {'success': False, 'message': str(e), 'output_path': ''}

        # 读取ZIP数据
        with open(zip_path, 'rb') as f:
            zip_data = f.read()

        # 确定输出扩展名
        ext = DISGUISE_TYPES[media_type]['ext']

        # 创建输出目录
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 输出文件路径
        output_file = output_path / f"{archive_name}{ext}"

        # 拼接载体数据 + ZIP数据
        with open(output_file, 'wb') as f:
            f.write(carrier_data)
            f.write(zip_data)

        return {
            'success': True,
            'message': f'伪装成功: {output_file}',
            'output_path': str(output_file)
        }

    except Exception as e:
        return {'success': False, 'message': f'伪装过程异常: {str(e)}', 'output_path': ''}

    except Exception as e:
        return {
            'success': False,
            'message': f'伪装过程异常: {str(e)}',
            'output_path': ''
        }


def process_packaging_with_disguise(
    source_paths: list[str],
    output_dir: str,
    archive_name: str,
    text_type: str,
    text_content: str = '',
    disguise_type: str = 'none',
    carrier_path: str = None
) -> dict:
    """
    执行完整打包流程（含伪装）:
    1. 生成随机密码
    2. 打包成加密7z
    3. 创建密码文件
    4. 创建说明文本文件
    5. 打包成存储模式zip
    6. 伪装处理（如果需要）
    7. 清理临时文件

    参数:
        source_paths: 源文件列表
        output_dir: 输出目录
        archive_name: 压缩包名称（不含扩展名）
        text_type: 文本类型
        text_content: 文本内容
        disguise_type: 伪装类型 (none/png/jpg/mp3/mp4/pdf)
        carrier_path: 自定义载体文件路径（可选，每次打包可指定不同载体）

    返回:
        dict: {
            'success': bool,
            'message': str,
            'password': str,
            'seven_z_path': str,
            'zip_path': str,
            'disguise_path': str
        }
    """
    # 先执行正常打包流程
    result = process_packaging(
        source_paths=source_paths,
        output_dir=output_dir,
        archive_name=archive_name,
        text_type=text_type,
        text_content=text_content
    )

    if not result['success']:
        return {
            **result,
            'disguise_path': ''
        }

    # 如果不需要伪装，直接返回
    if disguise_type == 'none' or not disguise_type:
        return {
            **result,
            'disguise_path': ''
        }

    # 执行伪装
    zip_path = result['zip_path']
    disguise_result = disguise_as_media(
        zip_path=zip_path,
        output_dir=output_dir,
        archive_name=archive_name,
        media_type=disguise_type,
        carrier_path=carrier_path
    )

    if disguise_result['success']:
        # 删除原始ZIP文件
        try:
            Path(zip_path).unlink()
        except Exception:
            pass

        return {
            'success': True,
            'message': f'打包并伪装成功: {disguise_result["output_path"]}',
            'password': result['password'],
            'seven_z_path': result['seven_z_path'],
            'zip_path': disguise_result['output_path'],
            'disguise_path': disguise_result['output_path']
        }
    else:
        return {
            'success': False,
            'message': f'打包成功但伪装失败: {disguise_result["message"]}',
            'password': result['password'],
            'seven_z_path': result['seven_z_path'],
            'zip_path': zip_path,
            'disguise_path': ''
        }
