# DSCode Assistant v0.6.0 Documentation Localization Report

[简体中文](DSCode_Assistant_v0.6.0_Documentation_Localization_Report.zh-CN.md)

## 1. Scope

This task prepares the public v0.6.0 documentation for international GitHub readers and Simplified Chinese users. English remains the default language for repository entry points. Every Chinese document is a complete reference rather than a line-by-line machine translation.

No application source code, database schema, provider request behavior, or version number was changed during the localization phase.

## 2. Modified files

- `README.md`
- `README.zh-CN.md`
- `CHANGELOG.md`
- `CHANGELOG_v0.6.0.md`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `docs/API配置说明.md`
- `docs/Windows_User_Guide.md`
- `docs/Windows构建与发布.md`
- `docs/常见问题.md`
- `docs/开发说明.md`
- `docs/用户使用说明.md`
- `docs/DSCode_Assistant_v0.6.0_Public_Release_Report.md`
- `docs/images/README.md`

## 3. Added files

- `CHANGELOG.zh-CN.md`
- `CHANGELOG_v0.6.0.zh-CN.md`
- `CONTRIBUTING.zh-CN.md`
- `CODE_OF_CONDUCT.zh-CN.md`
- `docs/README.md`
- `docs/README.zh-CN.md`
- `docs/API_Configuration.md`
- `docs/User_Guide.md`
- `docs/Development_Guide.md`
- `docs/FAQ.md`
- `docs/Windows_Build_and_Release.md`
- `docs/Windows_User_Guide.zh-CN.md`
- `docs/DSCode_Assistant_v0.6.0_Public_Release_Report.zh-CN.md`
- `docs/images/README.zh-CN.md`
- `docs/DSCode_Assistant_v0.6.0_Documentation_Localization_Report.md`
- `docs/DSCode_Assistant_v0.6.0_Documentation_Localization_Report.zh-CN.md`

## 4. English documentation improvements

- Keeps `README.md` as the default GitHub entry and states the local-first open-source positioning directly.
- Uses open-source project language for features, architecture, supported providers, Context Optimization, privacy, installation, configuration, and development.
- Adds English public guides for configuration, daily use, development, Windows builds, and frequently asked questions.
- Links English pages to their Simplified Chinese counterparts.
- Describes only behavior verified in the v0.6.0 codebase and explicitly marks Auto as an experimental placeholder that currently behaves as Raw.

## 5. Simplified Chinese synchronization

- Keeps `README.zh-CN.md` aligned with the English feature and privacy boundaries.
- Provides complete Chinese changelogs, contribution guidance, Code of Conduct, Windows guide, and public release report.
- Preserves the existing Chinese guides and links each one to its English counterpart.
- Uses natural Chinese technical writing instead of literal sentence-by-sentence translation.

## 6. Terminology

| English | Simplified Chinese |
| --- | --- |
| Context Optimization | 上下文优化 |
| provider / model provider | 模型提供商 |
| local-first | 本地优先 |
| API key | API 密钥 |
| OpenAI-compatible API | OpenAI 兼容接口 |

Class names, code identifiers, API paths, filenames, and exact user-interface labels retain their original spelling where required.

## 7. Consistency boundaries

- Raw preserves message order and content.
- Light performs deterministic cleanup and bounded short-message merging while protecting critical context.
- Auto is a stored experimental option and currently behaves as Raw.
- Token values displayed by DSCode Assistant are local estimates, not provider billing records.
- API keys remain in the operating-system credential store.
- Conversation history remains in local SQLite storage.
- The project has no mandatory account, telemetry, or DSCode-operated relay server.

## 8. Verification

The final verification covers:

- Markdown structure and trailing whitespace
- Local relative links
- English and Simplified Chinese document pairs
- Terminology consistency
- Version consistency
- Python syntax compilation and the existing test suite
- Sensitive credential and local-path patterns

Final results:

- Markdown files checked: 38
- Bilingual document pairs checked: 15
- Missing local links: 0
- Unbalanced fenced-code blocks: 0
- Trailing-whitespace findings: 0
- README and changelog heading-level comparison: passed
- Python compileall: passed
- Pytest: 119 passed, 1 skipped, 0 failed; 8 subtests passed

The skipped test covers project-indexer symlink handling. The current Windows account lacks symlink-creation privilege, so the test remains explicitly skipped rather than being reported as passed.
