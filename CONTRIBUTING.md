# Contributing to DSCode Assistant

[简体中文](CONTRIBUTING.zh-CN.md)

Thank you for contributing to DSCode Assistant. Keep changes focused, testable, and consistent with the project's local-first and privacy-first boundaries.

## Before opening an Issue

- Search existing Issues first.
- Include the DSCode Assistant version, operating system, reproduction steps, expected behavior, and actual behavior.
- Remove API keys, tokens, passwords, private source code, chat history, local databases, logs containing private content, personal paths, and unreviewed screenshots.
- Use the Bug Report or Feature Request template when applicable.

## Pull Requests

1. Fork the repository and create a focused branch from the latest public code.
2. Keep one complete feature, fix, or documentation change per Pull Request.
3. Preserve the no-account, no-telemetry, no-developer-relay design unless a public Issue explicitly discusses a boundary change.
4. Run the syntax check, full tests, and change-specific tests.
5. Review the staged files for credentials, user data, build output, caches, and generated databases.
6. Explain the reason for the change, compatibility impact, and actual test results.

Changes to provider request formats, the SQLite schema, `ChatWorker`, or privacy boundaries should be discussed in an Issue before implementation.

## Development checks

```powershell
python -m compileall -q dscode_assistant tests
python -m pytest -q
```

See the [development guide](docs/Development_Guide.md) for the current module layout and Windows build notes.

## Contact

- GitHub Issues: <https://github.com/suisui0601a-pixel/DSCode-Assistant/issues>
- International support: <dscode.assistant@gmail.com>
- 国内用户支持: <qwertyuiop076@163.com>
