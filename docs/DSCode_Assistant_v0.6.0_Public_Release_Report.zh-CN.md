# DSCode Assistant v0.6.0 公开发布报告

[English](DSCode_Assistant_v0.6.0_Public_Release_Report.md)

## 1. 发布范围

DSCode Assistant v0.6.0 是一次面向公开开源版本的维护发布，重点为本地上下文优化和仓库文档。现有 PySide6 桌面架构、SQLite 会话历史、模型提供商请求流程和操作系统凭据存储保持不变。

## 2. v0.6.0 公开能力

- Raw 与确定性 Light 上下文准备
- Light 模式清理空消息和无效占位消息
- 安全范围内的重复清理和连续短消息有限合并
- 保护关键指令、当前任务、最近回复、代码、补丁、错误、约束和文件引用
- 聊天界面的本地 Token 估算和临时保护统计
- Raw、Light 与预留 Auto 设置的旧配置兼容

Auto 在 v0.6.0 中不是自动优化策略，当前按 Raw 运行。本版本不宣称 AI 摘要、源码语义改写或固定 Token 减少比例。

## 3. 模型提供商架构

`ModelProvider` 契约保持不变。`DeepSeekProvider` 继续调用现有 `DeepSeekClient`；`OpenAICompatibleProvider` 支持用户配置兼容的 `/models` 和 `/chat/completions` 接口。`ChatWorker` 接收准备后的消息列表，并保持现有信号和线程模型。

项目继续使用 MIT License。

## 4. 测试结果

Windows 发布整理基线：

- Python compileall：通过
- Pytest：119 项通过，1 项跳过
- 失败测试：0
- 数据库迁移：不需要

跳过项用于验证项目索引器的符号链接处理。当前 Windows 账户没有创建符号链接的权限，因此该测试被明确跳过，而不是记录为通过。本次以文档和发布整理为主，没有重新构建 Windows 安装包和便携版。

## 5. 已知限制

- Auto 是配置占位，当前按 Raw 运行。
- Token 统计为本地估算，可能与模型提供商 usage 或账单不同。
- OpenAI 兼容实现存在差异，项目不承诺兼容所有接口。
- 仓库当前没有经过隐私审查的软件截图。
- 预构建发布包以 Windows 为主；macOS 和 Linux 当前从源码运行。

## 6. 后续公开维护方向

- 补充经过隐私审查的软件截图。
- 创建 GitHub Release 前重新构建并验证 v0.6.0 Windows 安装包和便携版。
- 继续测试不同 OpenAI 兼容接口的兼容性。
- 在不保存消息正文和不增加遥测的前提下完善上下文可观察性。
- 仅在确定性行为和安全边界可测试后实现 Auto。

以上方向不构成企业专属功能、商业计划或未完成内部能力的发布承诺。
