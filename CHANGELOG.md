# Changelog

All notable public changes to DSCode Assistant are documented here. Version numbers follow [Semantic Versioning](https://semver.org/).

[简体中文](CHANGELOG.zh-CN.md)

## [0.6.0] - 2026-08-16

### Context Optimization

- Added Raw and deterministic Light context-preparation modes.
- Added removal of empty messages, invalid placeholder messages, and safe consecutive duplicates.
- Added bounded merging of short consecutive messages without rewriting their content.
- Added critical-context protection rules and local protection statistics.
- Added local Token estimates and before/after comparisons in the chat interface.
- Preserved existing settings compatibility. Auto remains an experimental placeholder and currently behaves as Raw.

### Documentation and release preparation

- Made the English README the default project entry and added a complete Simplified Chinese README.
- Documented Context Optimization, model providers, privacy boundaries, installation, configuration, and development workflows.
- Added a Code of Conduct, screenshot contribution guidance, and standalone v0.6.0 release notes.
- Aligned Python package and Windows build metadata with v0.6.0.

## [0.4.0] - 2026-08-09

### Model-provider architecture

- Added the `ModelProvider` abstraction and `ProviderRegistry`.
- Added `DeepSeekProvider` and `OpenAICompatibleProvider`.
- Added provider, Base URL, API key, and model configuration controls.
- Kept OpenAI-compatible API keys in the operating-system credential store.
- Preserved the existing DeepSeek request flow.

## [0.1.0] - 2026-08-10

### Initial public release

- Added the PySide6 desktop chat interface and streaming model output.
- Added Markdown rendering, syntax highlighting, and copy actions.
- Added local SQLite conversation history and session management.
- Added operating-system credential storage for API keys.
- Added DeepSeek and OpenAI-compatible provider support.
- Added the localhost-only Automation interface.
- Added Windows portable and installer build workflows.
- Completed privacy, security, sensitive-information, and public-release checks.

> `v0.1.0` was the first public open-source release. The public version sequence began at 0.1.0 without removing stable features already present in the codebase.

## Links

- [v0.6.0 release notes](CHANGELOG_v0.6.0.md)
- [Simplified Chinese changelog](CHANGELOG.zh-CN.md)
