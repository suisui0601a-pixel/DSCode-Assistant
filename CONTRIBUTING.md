# 为 DSCode Assistant 贡献

感谢你关注 DSCode Assistant。项目由个人维护，提交清晰、范围明确的问题和改动有助于更快完成确认与合并。

## 提交 Issue

在创建新 Issue 前，请先搜索现有 Issue，确认问题或建议尚未被记录。然后选择对应模板：

- Bug：说明软件版本、操作系统、复现步骤、预期行为与实际行为。
- 功能建议：说明使用场景、需要解决的问题和期望结果。

请提供最小、可复现的信息。不要提交 API Key、Token、密码、私人代码、聊天记录、本地数据库、日志原文或含隐私的截图。

GitHub Issues：<https://github.com/suisui0601a-pixel/DSCode-Assistant/issues>

## 邮件反馈

无法使用 GitHub Issue 时，可通过以下邮箱反馈：

- International Support: <dscode.assistant@gmail.com>
- 国内用户支持：<qwertyuiop076@163.com>

邮件应包含简短标题、软件版本、操作系统和问题描述。请勿通过邮件发送凭据或未脱敏的私人数据。

## 参与贡献

1. Fork 仓库并从最新公开代码创建独立分支。
2. 一次改动只处理一个完整功能或明确修复。
3. 保持本地优先、无账号系统、无开发者服务器和无遥测的项目原则。
4. 提交前运行语法检查、单元测试及与改动相关的专项测试。
5. 检查提交中不包含 `.env`、API Key、Token、本地数据库、构建缓存或私人文件。
6. 创建 Pull Request，清楚说明改动原因、测试结果和兼容性影响。

涉及 API 请求格式、数据库结构、ChatWorker 线程模型或安全边界的改动，请先创建 Issue 讨论，不要在未说明影响的情况下直接大规模重构。

## 开发检查

```powershell
python -m compileall -q dscode_assistant tests
python -m unittest discover -s tests -v
```

详细开发说明参见 [docs/开发说明.md](docs/开发说明.md)。
