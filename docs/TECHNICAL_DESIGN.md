# 自动打包器 技术设计文档

基于项目架构模板 [`docs/PROJECT_ARCHITECTURE.md:1`](docs/PROJECT_ARCHITECTURE.md:1)，设计一份用于实现“自动打包器”桌面应用的详细技术设计文档。本设计仅包含技术规格和接口定义，供开发实现参考。

---

## 1. 概要

目标：实现一个桌面工具，支持用户拖入任意数量的文件/文件夹/压缩包，选择文本类型（说明文本 或 游戏简介），生成 10 位随机密码（A-Za-z0-9），对所有打包文件使用 7z 加密为 7z 格式，再生成密码文件（空文件，文件名为 解压：{密码}），生成说明文本文件，最后将 7z 压缩包、密码文件、说明文本以无压缩、无密码的方式打包成 zip，最后询问是否删除原始打包文件。

输出文件位置与命名由用户在 UI 中输入。对于单个拖入文件，UI 自动将其名称填入压缩包名称输入框。

引用：项目基础架构模板参考 [`docs/PROJECT_ARCHITECTURE.md:71`](docs/PROJECT_ARCHITECTURE.md:71) 中的 pywebview + AppApi 交互模式。

---

## 2. 项目结构（建议）

按模板组织，新增或调整如下文件/目录：

- [`script/gui.py:72`](script/gui.py:72) - 后端入口，暴露 AppApi
- [`script/core.py:13`](script/core.py:13) - 核心业务逻辑（打包、密码生成、命令执行）
- [`webui/index.html:15`](webui/index.html:15) - 前端主页面（HTML/CSS/JS）
- [`webui/components.js:1`](webui/components.js:1) - 前端组件与渲染逻辑（可合并到 index.html）
- [`config/setting.yaml:333`](config/setting.yaml:333) - 配置文件
- [`docs/TECHNICAL_DESIGN.md:1`](docs/TECHNICAL_DESIGN.md:1) - 本设计文档
- [`rundata/` ] - 运行时临时目录（输入、输出、工作区）
- [`scripts/setup.bat:133`](scripts/setup.bat:133) - 安装脚本（按模板）
- [`scripts/start.bat:221`](scripts/start.bat:221) - 启动脚本（按模板）

注：上述文件路径参照项目模板风格，实际实现时可按项目约定调整。

---

## 3. 后端 API 设计（`AppApi`）

说明：后端使用 Python 3.12，暴露给前端的类名为 `AppApi`（参见 [`script/gui.py:72`](script/gui.py:72)）。下列方法签名采用 JSON-serializable 输入/输出约定，所有返回统一格式：

{ "success": bool, "data": Any | null, "message": str | null }

方法列表（按功能分组）：

1) 初始化与配置
- get_initial_state(self, payload=None) -> dict
  - payload: None
  - 返回: { success, data: { state } }
  - 说明: 返回默认状态、上次输入路径、输出路径、UI 默认值等。

- load_config(self, payload=None) -> dict
  - payload: None
  - 返回: { success, data: { config } }

- save_config(self, payload: { config: dict }) -> dict
  - payload: { config }
  - 返回: { success }

2) 文件路径与拖放处理
- normalize_paths(self, payload: { items: [ { path: str } ] }) -> dict
  - payload: items 列表（前端拖入或选择）
  - 返回: { success, data: { items: [ { path, type, name, size, is_archive } ] } }
  - 说明: 识别文件/文件夹/压缩包，获取元信息，用于 UI 列表展示。

- pick_folder(self, payload=None) -> dict
  - 同模板，用于打开系统文件夹选择对话框

- pick_file(self, payload=None) -> dict
  - 同模板，用于打开文件选择对话框

3) 打包流程控制（核心接口）
- start_packaging(self, payload: {
    input_items: [ { path: str } ],
    text_type: str,           # '说明文本' 或 '游戏简介'
    sevenz_name: str,         # 用户输入的 7z 名称（不含扩展名）
    zip_name: str,            # 用户输入的 zip 名称（不含扩展名）
    output_dir: str,          # 输出目录（绝对路径）
    delete_originals: bool | null # 最后是否删除原始打包文件，null 表示弹窗后由前端确认
  }) -> dict
  - 返回: { success, data: { job_id: str }, message }
  - 说明: 触发完整打包流程，后端返回 job id 便于查询进度与日志。

- get_job_status(self, payload: { job_id: str }) -> dict
  - 返回: { success, data: { status: 'pending'|'running'|'done'|'failed', progress: int, logs: [str], result: { output_files: [str] } } }

- cancel_job(self, payload: { job_id: str }) -> dict
  - 返回: { success }

4) 辅助操作
- generate_password(self, payload: { length: int = 10 }) -> dict
  - 返回: { success, data: { password: str } }
  - 说明: 生成由 A-Za-z0-9 组成的随机密码，默认 10 位。

- create_password_file(self, payload: { password: str, dest_dir: str }) -> dict
  - 返回: { success, data: { path: str } }
  - 说明: 创建空文件，文件名为 `解压：{密码}`（使用全角冒号 '：'），返回生成路径。

- create_text_file(self, payload: { text_type: str, content: str | null, dest_dir: str, filename: str }) -> dict
  - 返回: { success, data: { path: str } }
  - 说明: 创建说明文本文件，若 content 为 null 则写入空文件。

5) 低级文件操作（供 core 调用，通常不直接暴露给前端）
- exec_command(self, payload: { cmd: [str], cwd: str | null, timeout: int | null }) -> dict
  - 返回: { success, data: { stdout: str, stderr: str, returncode: int } }


核心返回约定示例：
- 成功: { "success": true, "data": {...}, "message": null }
- 失败: { "success": false, "data": null, "message": "错误信息" }

---

## 4. 核心业务逻辑流程（后端流程说明）

以下以 `start_packaging` 为中心，描述详细执行步骤与边界条件：

1) 验证输入
  - 校验 payload 字段完整性（input_items 非空，sevenZName/zipName 非空或可自动填充，output_dir 可写）
  - 对于单个 input_item，若 sevenz_name 为空，自动填为该文件基名（去扩展名）
  - 检查输出目录磁盘空间、写权限

2) 规范化并拷贝到工作目录（Atomic 操作）
  - 在 output_dir 下创建临时工作目录 tmp_{job_id}
  - 将所有 input_items 的路径复制或软链接到工作目录。复制规则：
    - 若源为文件夹，复制整个文件夹
    - 若源为文件或压缩包，复制文件
  - 记录原始路径列表以便可能的回滚或删除

3) 密码生成
  - 调用 generate_password(length=10) 生成密码（A-Za-z0-9）

4) 7z 加密压缩
  - 构建 7z 命令，示例见第 5 节
  - 输出文件名: {sevenz_name}.7z（放在 output_dir 或 tmp 目录，最终移动到 output_dir）
  - 启用文件名加密（-mhe=on）以隐藏内文件名
  - 监控子进程输出，写入 job 日志

5) 生成密码文件
  - 文件名: `解压：{password}`（注意使用全角冒号，避免 Windows 禁止字符风险）
  - 在 tmp 工作目录创建空文件

6) 生成说明文本文件
  - 文件名: 由 text_type 决定，建议使用 "说明文本.txt" 或 "游戏简介.txt"
  - 内容由前端传入 content 字段或为空

7) ZIP 打包（无压缩、无密码）
  - 使用 7z 将 {sevenz_name}.7z、密码文件、说明文本打包成 {zip_name}.zip
  - 使用存储模式（无压缩），示例见第 5 节

8) 完成与清理
  - 将最终 ZIP 移动到 output_dir
  - 删除 tmp 工作目录（除非开启调试保留）
  - 如 payload.delete_originals 为 true，尝试删除用户原始 input_items（在删除前再次确认并记录错误）

9) 返回结果
  - 返回 job_id、输出文件绝对路径列表、日志

原子性与回滚：若在任一步骤失败，记录错误、保留 tmp 目录以便诊断、可选回滚已删除的原始文件（需谨慎，默认不回滚删除）。

---

## 5. 前端状态管理与 UI 组件划分

总体采用简单集中式状态管理（参考模板 [`docs/PROJECT_ARCHITECTURE.md:465`](docs/PROJECT_ARCHITECTURE.md:465)），不依赖框架。

State 对象建议结构：

state = {
  ui: {
    language: 'zh-CN',
    theme: 'light',
  },
  inputItems: [
    {
      id: str,            # 本地唯一 id
      path: str,          # 绝对或相对路径
      name: str,          # 基本名称
      type: 'file'|'folder'|'archive',
      size: int,
      status: 'pending'|'copied'|'error',
      error: str | null
    }
  ],
  selectedTextType: '说明文本' | '游戏简介',
  textContent: string | null,  # 可为空
  generatedPassword: string | null,
  sevenzName: string,    # 用户输入或自动填充
  zipName: string,       # 用户输入或自动填充
  outputDir: string,
  job: {
    id: string | null,
    status: 'idle'|'running'|'done'|'failed',
    progress: number,     # 0-100
    logs: [string]
  },
  uiFlags: {
    autoFillSingleName: true,
    confirmDeleteOriginals: null | bool
  }
}

UI 组件划分（建议）
- TopBar
  - 显示应用标题、设置按钮
- FileDropArea
  - 支持拖放、显示拖入文件个数
  - 当仅有 1 个文件时，自动触发 sevenzName 填充
- FileList
  - 展示 inputItems，支持移除、展开查看、重命名
- OptionsPanel
  - 文本类型单选框（说明文本 / 游戏简介）
  - 文本内容编辑框（可选折叠）
- NameInputs
  - sevenzName 输入框（必填，支持自动填充）
  - zipName 输入框（必填）
- ActionButtons
  - 生成密码（按钮，调用 generate_password）
  - 开始打包（按钮，调用 start_packaging）
  - 取消/清空
- ProgressPanel
  - 实时日志、进度条
- ConfirmDialog
  - 在操作完成后询问是否删除原始打包文件（若 payload.delete_originals 为 null）

UI 风格要点
- 精炼、窄而高效的控件宽度，不要元素过宽
- 列表项与操作按钮紧凑排列
- 拖放区与文件列表占据主要垂直空间

前端与后端交互示例（伪流程）
1. window.pywebviewready -> 调用 get_initial_state
2. 用户拖入文件 -> normalize_paths -> 更新 state.inputItems
3. 用户确认参数 -> 调用 start_packaging，后端返回 job_id
4. 前端轮询 get_job_status 或通过长轮询接收进度，更新日志/进度条
5. 操作完成后，展示 ConfirmDialog 询问是否删除原始文件

---

## 6. 7z 命令行参数（示例）

说明：后端使用系统安装的 7z 可执行程序。若打包为 EXE，建议在安装脚本中携带 7z 可执行文件或在配置中允许用户指定 7z 路径（config/setting.yaml）。

1) 7z 加密压缩为 7z（建议使用 AES-256，隐藏文件名）

示例命令：

- Windows cmd 示例（将多个文件/文件夹打包为加密 7z）：
  - 7z a -t7z "{output_path}\{sevenz_name}.7z" "{file1}" "{file2}" -p{PASSWORD} -mhe=on -mx=9

说明：
- a: 添加/创建压缩包
- -t7z: 指定 7z 格式
- -p{PASSWORD}: 指定密码（注意不要在日志中明文打印密码）
- -mhe=on: 加密文件名，防止列出压缩包内文件名
- -mx=9: 最大压缩级别（可配置为 1-9）

注意安全：尽量避免将密码作为整个命令行的一部分写入持久日志，建议通过 stdin 或临时环境变量传递；但 7z 的命令行通常使用 -p 参数，若关心更高安全性，可考虑先将密码写入临时响应文件并以 @responsefile 的方式传参（需清理该文件）。

2) 将文件打包为 zip 且使用存储模式（无压缩、无密码）

示例命令：

- 7z a -tzip "{output_path}\{zip_name}.zip" "{sevenz_archive}" "{pw_file}" "{text_file}" -mx=0

说明：
- -tzip: 指定 zip 格式
- -mx=0: 设置无压缩（存储模式），兼容性高
- 不传 -p 或 -mem= 可以保证无密码

3) 其他常用选项
- -y: 自动回答所有提示为 yes（谨慎使用）
- -ssw: 在压缩时使用共享模式以便读取仍被占用的文件（限定情况下使用）
- -bd: 禁止显示进度条输出（便于解析 stdout）

---

## 7. 配置文件结构（`config/setting.yaml`）

建议内容：

app_settings:
  app_name: 自动打包器
  language: zh-CN
  theme: light
  sevenz_path: ""    # 为空则使用系统 PATH 中的 7z
  temp_dir: ./rundata/tmp

user_settings:
  last_input_paths: []
  last_output_dir: ./rundata/output
  last_text_type: 说明文本
  default_compression_level: 9
  keep_tmp_on_error: true
  default_delete_originals: false

ui_tips:
  - "拖入文件或文件夹到主区域"
  - "单个文件时会自动填充压缩名称"

安全与权限:
  allow_overwrite_output: false

---

## 8. 错误处理与日志策略

1) 错误分类
- 可恢复错误（Recoverable）: 临时 I/O 错误、磁盘空间不足警告、单个文件复制失败
- 不可恢复错误（Fatal）: 7z 执行返回非零且无法继续、路径权限不足

2) 错误处理原则
- 所有 API 返回统一结构 { success, data, message }
- 记录详细日志（包含时间戳、阶段标签、命令、非敏感 stdout/stderr）
- 对于包含敏感信息（如密码）的日志，记录时用占位符替代或将密码做掩码处理
- 对于可恢复错误，尝试有限重试（例如文件复制最多 2 次），并在 UI 中提示用户采取操作
- 对于不可恢复错误，停止作业、将 tmp 目录保留供诊断（依据配置决定是否自动删除）

3) 日志级别
- DEBUG: 详细命令、子进程输出（仅在 debug 模式）
- INFO: 关键流程步骤（开始、完成、输出文件路径）
- WARN: 可恢复问题
- ERROR: 致命错误与堆栈信息

4) 原子性与回滚
- 使用 tmp 工作目录执行所有可变操作，只有在全部成功后再移动到最终输出目录
- 删除原始文件仅在所有步骤成功且用户确认后执行
- 若删除失败，记录错误并提示用户手动清理

5) 前端错误提示
- API 返回失败时，弹出错误提示并在 ProgressPanel 显示详细日志
- 对于已识别的常见错误（路径不存在、权限拒绝、7z 未安装），提供具体解决建议

---

## 9. 安全与平台兼容注意事项

- Windows 文件名禁止字符（例如 ASCII 冒号 : 等）需要避免。文档中要求的文件名格式为 `解压：{密码}`，请使用全角冒号 '：'（U+FF1A），保证 Windows 平台可用并满足视觉要求。
- 密码在内存中处理时应尽量缩短生命周期，避免写入持久日志或临时文件。如果确实需要写入，应使用受限权限的临时目录并在使用后立即删除。
- 若系统中不存在 7z，可在安装脚本中随应用分发 7z 可执行文件，或在配置中让用户指定路径（`app_settings.sevenz_path`）。

---

## 10. 可扩展性与后续迭代建议

- 支持多线程任务队列，允许批量提交多个打包作业
- 支持导入/导出作业模板（压缩级别、文本模板、是否删除源）
- 增加本地化支持（多语言）
- 在 UI 中增加 drag-preview 和文件内容预览（对于文本、小文件）

---

## 11. 参考

- 项目通用模板 [`docs/PROJECT_ARCHITECTURE.md:1`](docs/PROJECT_ARCHITECTURE.md:1)





