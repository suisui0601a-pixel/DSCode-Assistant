# 为 DSCode Assistant 贡献代码

[English](CONTRIBUTING.md)

感谢你参与改进 DSCode Assistant。所有贡献都应保持项目本地优先、隐私优先的桌面架构。

## 提交 Issue 前

- 请先搜索现有 Issue。
- Bug 报告应包含软件版本、操作系统、复现步骤、预期行为和实际行为。
- 发布前请移除 API 密钥、Token、密码、私人源码、聊天历史、本地数据库、包含私人内容的日志、本机路径和未审查截图。
- 请根据问题类型选择 Bug Report 或 Feature Request 模板。

GitHub Issues：<https://github.com/suisui0601a-pixel/DSCode-Assistant/issues>

## Pull Request

1. Fork 仓库，并从最新公开代码创建职责单一的分支。
2. 一个 Pull Request 只处理一项完整功能、修复或文档改动。
3. 保持无账号、无遥测、无开发者中转服务的设计；如需调整这些边界，应先在公开 Issue 中讨论。
4. 运行语法检查、完整测试和与改动相关的专项测试。
5. 检查暂存文件中没有凭据、用户数据、构建产物、缓存和生成的数据库。
6. 说明修改原因、兼容性影响和实际测试结果。

如需修改模型提供商请求格式、SQLite 结构、`ChatWorker` 或隐私边界，请先创建 Issue 讨论。

## 开发检查

```powershell
python -m compileall -q dscode_assistant tests
python -m pytest -q
```

项目模块和 Windows 构建说明参见[开发说明](docs/开发说明.md)。

## 联系方式

- GitHub Issues：<https://github.com/suisui0601a-pixel/DSCode-Assistant/issues>
- International support：<dscode.assistant@gmail.com>
- 国内用户支持：<qwertyuiop076@163.com>

请勿通过邮件发送凭据或未脱敏的私人源码。
