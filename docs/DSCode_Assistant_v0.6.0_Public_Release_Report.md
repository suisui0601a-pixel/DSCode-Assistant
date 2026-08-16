# DSCode Assistant v0.6.0 Public Release Report

[简体中文](DSCode_Assistant_v0.6.0_Public_Release_Report.zh-CN.md)

## 1. Release scope

DSCode Assistant v0.6.0 is a public open-source maintenance release focused on local Context Optimization and repository documentation. It preserves the existing PySide6 desktop architecture, SQLite history, provider request flow, and operating-system credential storage.

## 2. Modified files

- `pyproject.toml`
- `dscode_assistant/__init__.py`
- `build_windows.bat`
- `installer.iss`
- `windows_version_info.txt`
- `README.md`
- `CHANGELOG.md`
- `CONTRIBUTING.md`
- `docs/Windows_User_Guide.md`
- `docs/Windows构建与发布.md`
- `docs/开发说明.md`
- `docs/用户使用说明.md`
- `docs/API配置说明.md`
- `docs/常见问题.md`

## 3. New files

- `README.zh-CN.md`
- `CHANGELOG.zh-CN.md`
- `CODE_OF_CONDUCT.md`
- `CODE_OF_CONDUCT.zh-CN.md`
- `CHANGELOG_v0.6.0.md`
- `CHANGELOG_v0.6.0.zh-CN.md`
- `CONTRIBUTING.zh-CN.md`
- `docs/README.md`
- `docs/README.zh-CN.md`
- `docs/API_Configuration.md`
- `docs/User_Guide.md`
- `docs/Development_Guide.md`
- `docs/FAQ.md`
- `docs/Windows_Build_and_Release.md`
- `docs/Windows_User_Guide.zh-CN.md`
- `docs/images/README.md`
- `docs/images/README.zh-CN.md`
- `docs/DSCode_Assistant_v0.6.0_Public_Release_Report.md`
- `docs/DSCode_Assistant_v0.6.0_Public_Release_Report.zh-CN.md`
- `docs/DSCode_Assistant_v0.6.0_Documentation_Localization_Report.md`
- `docs/DSCode_Assistant_v0.6.0_Documentation_Localization_Report.zh-CN.md`

## 4. Public v0.6.0 capabilities

- Raw and deterministic Light context preparation
- Removal of empty and invalid placeholder messages in Light mode
- Safe duplicate cleanup and bounded merging of short same-role messages
- Protection of critical instructions, current tasks, recent replies, code, patches, errors, constraints, and file references
- Local token estimates and transient protection statistics in the chat UI
- Settings compatibility for Raw, Light, and the reserved Auto option

Auto is not an automatic optimization strategy in v0.6.0. It currently behaves as Raw. The release does not claim AI summarization, semantic source-code rewriting, or a fixed Token reduction percentage.

## 5. Provider architecture

The `ModelProvider` contract remains unchanged. `DeepSeekProvider` delegates to the existing `DeepSeekClient`; `OpenAICompatibleProvider` supports configurable compatible `/models` and `/chat/completions` endpoints. `ChatWorker` receives the prepared message list and retains its existing signal and threading model.

The existing MIT License was reviewed and remains unchanged.

## 6. Test results

Release-preparation baseline on Windows:

- Python compileall: passed
- Pytest: 119 passed, 1 skipped
- Failed tests: 0
- Database schema migration: not required

The skipped test covers symlink handling in the project indexer and was skipped because the current Windows account does not have symlink-creation privilege. It is preserved rather than reported as a pass. Windows installer and portable artifacts were not rebuilt as part of this documentation-focused release preparation.

## 7. Known issues and limitations

- Auto is a configuration placeholder and currently behaves as Raw.
- Token statistics are local estimates and may differ from provider usage or billing records.
- OpenAI-compatible implementations may vary; compatibility with every endpoint is not guaranteed.
- The repository currently has no privacy-reviewed application screenshots.
- Prebuilt public packages focus on Windows; macOS and Linux are source-run workflows.

## 8. Public follow-up direction

Non-binding public maintenance priorities:

- Add privacy-reviewed screenshots.
- Rebuild and verify v0.6.0 Windows installer and portable artifacts before creating a GitHub Release.
- Continue compatibility tests for OpenAI-compatible endpoints.
- Improve context observability without storing message content or adding telemetry.
- Implement Auto only after its deterministic behavior and safety boundaries are testable.

This report does not announce enterprise-only features, commercial plans, or unfinished internal capabilities.
