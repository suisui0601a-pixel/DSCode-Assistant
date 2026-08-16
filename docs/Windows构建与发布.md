# DSCode Assistant Windows 构建与发布

[English](Windows_Build_and_Release.md)

本文档描述 DSCode Assistant `0.6.0` 的 Windows 本地构建流程。构建产物不包含用户配置、API 密钥、聊天记录或 SQLite 数据库。

## 构建环境

- Windows 10/11 x64
- Python 3.11 或更高版本
- Inno Setup 6（用于生成安装程序）
- 可访问 PyPI（构建脚本会安装运行依赖与 PyInstaller）

## 启动入口

开发环境使用：

```powershell
python -m dscode_assistant
```

PyInstaller 生成的入口调用 `dscode_assistant.app.main()`，与模块启动逻辑一致。

## 一键构建

在项目根目录运行：

```bat
build_windows.bat
```

脚本会依次执行：

1. 创建或复用 `.build-venv` 隔离环境。
2. 安装 `requirements.txt` 与最新版 PyInstaller。
3. 清理临时 `build`、`dist` 和当前版本的发布目录。
4. 生成 PyInstaller onedir 可执行程序。
5. 打包本地资源、PySide6、Markdown、Pygments、Bleach 与 keyring。
6. 检查便携目录中不存在 `settings.json`、数据库或日志数据。
7. 生成便携版 ZIP。
8. 调用 Inno Setup 生成安装程序。

## 产物

```text
release/
├── DSCode Assistant Setup v0.6.0.exe
├── DSCode Assistant v0.6.0 Portable.zip
└── v0.6.0/
    └── portable/
        ├── DSCode Assistant.exe
        ├── LICENSE.txt
        ├── Windows_User_Guide.md
        └── _internal/
```

## 数据与凭据路径

- 普通设置：`%APPDATA%\DSCodeAssistant\settings.json`
- SQLite 历史：`%APPDATA%\DSCodeAssistant\dscode_assistant.db`
- 启动异常诊断：`%APPDATA%\DSCodeAssistant` 下的本地诊断文件
- API 密钥：Windows 凭据管理器，由 `keyring` 的 Windows 后端保存

安装目录和便携版目录都不保存用户 API 密钥。安装版和便携版使用相同的本地用户数据目录，因此升级或切换版本时可以继续读取原有配置和历史记录。

## 发布前验证

建议至少执行：

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m compileall -q dscode_assistant tests
python -m pytest -q
```

还应完成以下 Windows 专项检查：

- 便携版启动与关闭。
- 首次启动创建用户数据目录。
- 图标、QSS 和 Markdown 资源加载。
- Windows 凭据管理器后端可用。
- 安装目录选择、桌面快捷方式和开始菜单入口。
- 安装程序静默安装与卸载。
- 发布目录中不存在用户数据和敏感文件。

## 注意事项

- 当前产物未进行代码签名，Windows SmartScreen 可能显示未知发布者提示。
- 构建脚本仅清理临时构建目录和当前版本产物，不删除其他版本发布包。
- 卸载程序默认保留 `%APPDATA%\DSCodeAssistant`，防止误删聊天记录与设置。
