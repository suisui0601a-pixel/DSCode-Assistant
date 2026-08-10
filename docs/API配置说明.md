# DSCode Assistant API 配置说明

## DeepSeek 官方 API

1. 在 DeepSeek 开放平台创建个人 API Key。
2. 打开 DSCode Assistant 设置页。
3. 选择“DeepSeek”。
4. 输入 API Key、模型名称、Temperature 和 Max Tokens。
5. 测试连接后保存。

默认 API 地址由客户端固定为：

```text
https://api.deepseek.com
```

软件不会把 DeepSeek API Key 发送到开发者服务器。请求由用户电脑直接发往 DeepSeek 官方 API。

## OpenAI Compatible

需要配置：

- Base URL
- Model Name
- API Key（服务端需要鉴权时）
- Temperature
- Max Tokens

本地服务示例：

```text
http://127.0.0.1:11434/v1
```

请只使用可信服务地址。远程 Base URL 会收到用户主动发送的会话上下文，其数据处理规则由该服务提供方决定。

## 凭据存储

所有提供商 API Key 均通过 Python `keyring` 保存到操作系统凭据库：

- Windows：Windows Credential Manager
- macOS：Keychain
- Linux：可用的 Secret Service/keyring 后端

API Key 不应写入 `.env`、源代码、测试文件、`settings.json` 或数据库。

## 常见连接问题

- `401`：API Key 无效或缺失。
- `402`：账户余额不足或服务不可用。
- `404`：Base URL 或模型名称不存在。
- `429`：请求频率过高。
- 超时：检查网络、模型服务状态和请求超时配置。

模型名称、价格、限额和可用性可能变化，请以对应服务提供商的官方文档为准。
