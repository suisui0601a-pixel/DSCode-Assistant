# DSCode Assistant

DSCode Assistant 是一个使用 Python 与 PySide6 开发的本地优先 DeepSeek API 编程助手。软件直接连接 DeepSeek 官方 API，不提供开发者服务器，不建立用户账号，也不收集遥测数据。

## 功能

- DeepSeek 流式聊天与停止生成
- Markdown 显示、代码高亮与一键复制
- Python、FastAPI、Debug、代码优化、SQL、算法等内置提示模板
- 本地 SQLite 会话历史、搜索与重命名
- 使用系统凭据库安全保存 API Key
- 模型、Temperature 和 Max Tokens 设置
- Windows 便携版及安装版发布流程

## 使用方式

### Windows 安装版

1. 下载 `DSCode Assistant Setup.exe`。
2. 运行安装程序并选择安装目录。
3. 从开始菜单或桌面快捷方式启动软件。
4. 在设置中填写自己的 DeepSeek API Key，并测试连接。

### Windows 便携版

1. 下载并解压 `release.zip`。
2. 运行 `DSCode Assistant.exe`。
3. 不要只复制 EXE；便携目录中的 `_internal` 文件夹也是运行所必需的。

### 从源码运行

需要 Python 3.11 或更高版本：

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m dscode_assistant
```

## API Key 配置

请在 [DeepSeek 开放平台](https://platform.deepseek.com/) 创建自己的 API Key。首次启动后进入“设置”，填写 API Key 并保存。API Key 由操作系统凭据库管理，不会写入 `settings.json` 或 SQLite 数据库。

软件的网络请求仅发往 DeepSeek 官方 API：`https://api.deepseek.com`。使用 API 产生的费用由 DeepSeek 官方按照用户自己的账户计费。

## 数据与隐私

- 聊天记录、设置和诊断信息仅保存在用户电脑。
- Windows 数据目录为 `%APPDATA%\DSCodeAssistant`。
- 聊天记录保存在本地 SQLite 数据库中。
- 普通设置保存在本地 `settings.json` 中。
- API Key 保存在系统凭据库中。
- 软件没有账号系统、开发者服务器、遥测或数据回传功能。
- 隐私安全异常日志不记录聊天内容、API Key、请求体或异常消息。

卸载程序不会主动删除用户数据。如需彻底清除，可在软件中清理历史，并在卸载后手动删除上述数据目录及系统凭据库中的 DSCode Assistant 凭据。

## 本地 Automation 接口

应用启动后会在 `127.0.0.1:18765` 提供仅限本机访问的 JSON 接口，供本地工具唤醒 DSC、选择项目并创建待确认的编程任务。任务只会预填到输入框，不会自动调用 DeepSeek API。

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `GET` | `/v1/status` | 检测应用、项目、会话及生成状态 |
| `POST` | `/v1/app/activate` | 显示并激活 DSC 窗口 |
| `POST` | `/v1/projects/open` | 设置当前项目，JSON：`{"path":"D:\\Project"}` |
| `POST` | `/v1/tasks` | 创建任务草稿，JSON：`{"title":"任务名","instruction":"任务内容","project_path":"D:\\Project"}` |

该接口不监听局域网地址，不提供 AI 服务端或 Agent 能力，也不会自动发送任务内容。

## 模型提供商扩展接口

`dscode_assistant.model_providers` 提供统一的 `ModelProvider` 流式聊天接口：

- `DeepSeekProvider`：包装现有 `DeepSeekClient`，不改变当前 GUI 默认调用链。
- `OpenAICompatibleProvider`：支持标准 `/models` 与 `/chat/completions` 接口，可连接远程兼容服务，也可连接本机兼容端点。
- `ProviderRegistry`：供后续按需注册新的远程服务或本地模型适配器。

设置页面可选择 DeepSeek 或 OpenAI Compatible，并分别配置模型与系统凭据库中的 API Key；OpenAI Compatible 还支持自定义 Base URL。旧版设置缺少提供商字段时仍默认使用 DeepSeek。本阶段不包含模型下载、模型管理、GPU 调度或自动切换功能。

## 构建 Windows 版本

运行：

```bat
build_windows.bat
```

脚本会创建独立构建环境、安装依赖，并按当前版本生成：

- `release\v<版本号>\portable\`：PyInstaller 便携目录。
- `release\DSCode v<版本号> Portable.zip`：便携版压缩包。
- `release\DSCode v<版本号>.exe`：由 Inno Setup 6 生成的安装包。

构建只清理当前版本目录和同名产物，不会删除 `release` 中已有的旧安装包。

## 开源协议

本项目采用 [MIT License](LICENSE)。允许个人和商业使用、修改及再分发，但必须保留原始版权和许可声明。本项目无盈利目的，且不对 DeepSeek 官方服务的可用性或费用承担责任。
