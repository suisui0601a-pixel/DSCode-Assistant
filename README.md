# DSCode Assistant

DSCode Assistant 是一款开源、免费、本地优先的桌面 AI 编程助手。应用使用 Python 与 PySide6 开发，默认由用户电脑直接连接 DeepSeek 官方 API，也可连接 OpenAI Compatible 接口。

项目不提供开发者服务器，不建立用户账号，不收集遥测数据，不上传 API Key。聊天记录和普通设置仅保存在用户电脑；只有用户主动发送的当前会话上下文会提交给所选模型服务。

当前公开版本：`v0.1.0`

## 功能列表

- DeepSeek 流式聊天、停止生成和错误提示
- Markdown 渲染、代码高亮、代码与消息复制
- Python、FastAPI、Debug、代码优化、代码解释、SQL、算法等提示模板
- SQLite 本地会话历史、搜索、重命名与删除
- 使用操作系统凭据库保存 API Key
- DeepSeek 与 OpenAI Compatible 提供商配置
- 模型、Temperature、Max Tokens 设置
- 仅监听 `127.0.0.1` 的本地 Automation 接口
- Windows 便携版与安装包构建流程

## 隐私与安全

- API Key 由 `keyring` 写入操作系统凭据库，不写入 `settings.json` 或 SQLite。
- Windows 用户数据目录为 `%APPDATA%\DSCodeAssistant`。
- 项目没有账号系统、开发者服务器、遥测、统计或数据回传功能。
- 隐私安全异常日志不记录聊天正文、API Key、请求体或异常原文。
- DeepSeek 模式只访问 `https://api.deepseek.com`；OpenAI Compatible 模式访问用户自行配置的 Base URL。

使用第三方或自建模型服务时，请自行确认其隐私政策、网络边界和计费规则。

## 安装方式

### Windows 安装版

1. 从 GitHub Release 下载 `DSCode v0.1.0.exe`。
2. 运行安装程序并选择安装目录。
3. 按需创建桌面快捷方式。
4. 启动应用并完成模型配置。

### Windows 便携版

1. 下载 `DSCode v0.1.0 Portable.zip`。
2. 解压完整目录。
3. 运行 `DSCode Assistant.exe`。

请保留便携目录中的 `_internal` 文件夹，不要只复制 EXE。

### 从源码运行

需要 Python 3.11 或更高版本：

```powershell
git clone https://github.com/suisui0601a-pixel/DSCode-Assistant.git
cd DSCode-Assistant
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m dscode_assistant
```

macOS 与 Linux 可使用对应平台的虚拟环境激活命令。当前发布包以 Windows 为主，源码运行仍需系统具备 Qt/PySide6 所需图形环境。

## 使用方式

1. 打开“设置”。
2. 选择模型提供商。
3. DeepSeek 用户填写自己的 API Key；OpenAI Compatible 用户填写 Base URL、API Key（如需要）和模型名。
4. 测试连接并保存设置。
5. 新建会话，选择提示模板并发送编程问题。
6. 历史会话会自动保存在本机 SQLite 数据库中。

详细步骤参见 [用户使用说明](docs/用户使用说明.md)。

## 配置说明

### DeepSeek

请在 [DeepSeek 开放平台](https://platform.deepseek.com/) 创建 API Key。软件不会附带公共 Key，也不会通过开发者服务器中转请求。

### OpenAI Compatible

设置页支持自定义 Base URL、API Key 和 Model Name。Base URL 应包含兼容接口所需的版本路径，例如 `http://127.0.0.1:11434/v1`。本机无鉴权服务可以留空 API Key。

更多说明参见 [API 配置说明](docs/API配置说明.md)。

## 本地 Automation 接口

应用启动后在 `127.0.0.1:18765` 提供本机 JSON 接口，用于激活窗口、选择项目和创建待确认的任务草稿。该接口不监听局域网地址，不执行 Agent 逻辑，也不会自动调用模型 API。

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `GET` | `/v1/status` | 获取应用、项目、会话和生成状态 |
| `POST` | `/v1/app/activate` | 显示并激活应用窗口 |
| `POST` | `/v1/projects/open` | 设置当前项目，示例：`{"path":"<project-path>"}` |
| `POST` | `/v1/tasks` | 创建任务草稿，示例：`{"title":"任务名","instruction":"任务内容","project_path":"<project-path>"}` |

## 截图位置

公开发布截图统一放在 `docs/images/`：

- `docs/images/main-window.png`：主聊天窗口
- `docs/images/settings.png`：模型设置页面

提交截图前必须确认画面中没有 API Key、私人路径、聊天隐私或其他个人信息。仓库当前不附带演示截图，避免使用未经脱敏的本机画面。

## 开发说明

项目保持小型、直接的桌面应用结构，不引入服务器、账号系统或遥测服务。开发前请阅读 [开发说明](docs/开发说明.md)。

常用检查：

```powershell
python -m compileall -q dscode_assistant tests
python -m unittest discover -s tests -v
```

Windows 打包：

```bat
build_windows.bat
```

构建产物输出到 `release/`，该目录不会进入 Git。

## 项目文档

- [用户使用说明](docs/用户使用说明.md)
- [开发说明](docs/开发说明.md)
- [API 配置说明](docs/API配置说明.md)
- [常见问题](docs/常见问题.md)
- [贡献指南](CONTRIBUTING.md)
- [版本变更记录](CHANGELOG.md)
- [v0.1.0 版本说明](RELEASE_NOTES_v0.1.0.md)

## 联系方式

Bug、功能建议和可复现的问题请优先通过 [GitHub Issues](https://github.com/suisui0601a-pixel/DSCode-Assistant/issues) 提交。提交前请移除 API Key、Token、私人代码、本地数据库及其他敏感信息。

### International Support

Email: [dscode.assistant@gmail.com](mailto:dscode.assistant@gmail.com)

### 国内用户支持

邮箱：[qwertyuiop076@163.com](mailto:qwertyuiop076@163.com)

## 开源协议

项目采用 [MIT License](LICENSE)。选择 MIT 的原因是协议简洁、依赖兼容性好，适合个人维护的免费公益项目，也便于社区学习、修改和分发。

项目本身无盈利目的，但 MIT 是标准开源协议，**不会禁止商业使用**。任何分发者都必须保留原始版权与许可声明，软件按“原样”提供，不附带担保。

## 免责声明

DSCode Assistant 与 DeepSeek 官方不存在隶属或担保关系。模型服务可用性、输出质量、内容合规和 API 费用由对应服务提供商及用户账户规则决定。请勿向模型服务发送无权处理的代码、密钥或个人数据。
