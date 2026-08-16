# DSCode Assistant Development Guide

[简体中文](开发说明.md)

## 1. Engineering principles

- Keep the application local-first; do not add a developer-operated relay server.
- Do not add mandatory accounts, telemetry, or user-behavior analytics.
- Store API keys only in the operating-system credential store.
- Prefer direct, testable modules over unnecessary abstraction.
- Keep GUI, database, network, and core behavior boundaries clear.

## 2. Environment setup

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m dscode_assistant
```

## 3. Main modules

| File | Responsibility |
| --- | --- |
| `app.py` | QApplication startup, dependency assembly, and resource cleanup |
| `main_window.py` | Main window and conversation management |
| `chat_widget.py` | Chat interaction, message lifecycle, and ChatWorker integration |
| `api_client.py` | Official DeepSeek API communication and stream parsing |
| `model_providers.py` | Model-provider abstraction and OpenAI-compatible adapter |
| `context/` | Deterministic context preparation, Token estimation, and message protection |
| `languages/` | Local language metadata and detection hints |
| `database.py` | SQLite initialization and history persistence |
| `settings.py` | Ordinary settings, data paths, and credential-store access |
| `markdown_renderer.py` | Markdown rendering, highlighting, and sanitization |
| `automation.py` | Localhost-only Automation interface |

## 4. Verification

```powershell
python -m compileall -q dscode_assistant tests
python -m pytest -q
```

For offscreen UI tests:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest -q
```

## 5. Security review

Before committing, check for:

- `.env`, API keys, tokens, passwords, and private keys
- `settings.json`, SQLite databases, and logs
- local absolute paths, personal addresses, and unreviewed screenshots
- virtual environments and generated `build/`, `dist/`, or `release/` directories

Tests must use clearly invalid placeholder credentials and must not call a real account.

## 6. Build for Windows

After installing Inno Setup 6, run:

```bat
build_windows.bat
```

The script creates an isolated build environment and generates a versioned portable package under `release/`. It also generates an installer when Inno Setup is available.

## 7. Contribution guidance

Keep each commit focused on one complete feature or clear fix. Run relevant tests and do not commit generated files or user data. Discuss database-schema, API-format, or threading-model changes in an Issue before implementation.
