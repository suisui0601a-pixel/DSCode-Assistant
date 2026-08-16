# 变更记录

本文记录 DSCode Assistant 的主要公开变更。版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

[English](CHANGELOG.md)

## [0.6.0] - 2026-08-16

### 上下文优化

- 新增 Raw 与确定性 Light 上下文准备模式。
- 新增空消息、无效占位消息和安全范围内连续重复消息的清理。
- 新增连续短消息的有限合并，不改写消息正文。
- 新增关键上下文保护规则和本地保护统计。
- 新增聊天界面的本地 Token 估算与优化前后对比。
- 保持旧设置兼容；Auto 仍为实验占位，当前按 Raw 运行。

### 文档与发布整理

- 将英文 README 作为默认项目入口，并新增完整的简体中文 README。
- 补充上下文优化、模型提供商、隐私边界、安装、配置和开发说明。
- 新增行为准则、截图贡献说明和 v0.6.0 独立版本说明。
- 将 Python 包与 Windows 构建元数据统一为 v0.6.0。

## [0.4.0] - 2026-08-09

### 模型提供商架构

- 新增 `ModelProvider` 抽象接口与 `ProviderRegistry`。
- 新增 `DeepSeekProvider` 和 `OpenAICompatibleProvider`。
- 新增模型提供商、Base URL、API 密钥和模型配置控件。
- OpenAI 兼容接口的 API 密钥继续保存在操作系统凭据库。
- 保持现有 DeepSeek 请求流程兼容。

## [0.1.0] - 2026-08-10

### 首次公开版本

- 新增 PySide6 桌面聊天界面和流式模型输出。
- 新增 Markdown 渲染、代码高亮和复制功能。
- 新增 SQLite 本地会话历史和会话管理。
- 新增通过操作系统凭据库存储 API 密钥。
- 新增 DeepSeek 与 OpenAI 兼容接口支持。
- 新增仅限 localhost 的 Automation 接口。
- 新增 Windows 便携版与安装包构建流程。
- 完成隐私、安全、敏感信息和公开发布检查。

> `v0.1.0` 是首个公开开源版本。公开版本号从 0.1.0 开始，不代表移除代码库中已经存在的稳定功能。

## 相关链接

- [v0.6.0 版本说明](CHANGELOG_v0.6.0.zh-CN.md)
- [English changelog](CHANGELOG.md)
