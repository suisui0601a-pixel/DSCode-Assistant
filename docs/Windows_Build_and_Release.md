# DSCode Assistant Windows Build and Release

[简体中文](Windows构建与发布.md)

This guide describes the local Windows build workflow for DSCode Assistant v0.6.0. Build outputs do not include user settings, API keys, conversation history, or SQLite databases.

## Build environment

- Windows 10 or 11 x64
- Python 3.11 or later
- Inno Setup 6 for the installer
- PyPI access, because the build script installs runtime dependencies and PyInstaller

## Application entry point

Source execution uses:

```powershell
python -m dscode_assistant
```

The PyInstaller entry calls `dscode_assistant.app.main()`, matching the module startup flow.

## Build command

Run from the repository root:

```bat
build_windows.bat
```

The script:

1. Creates or reuses an isolated `.build-venv`.
2. Installs `requirements.txt` and PyInstaller.
3. Cleans temporary `build`, `dist`, and the current version's release directory.
4. Creates the PyInstaller onedir application.
5. Includes local assets, PySide6, Markdown, Pygments, Bleach, and keyring.
6. Verifies that the portable directory has no settings, database, or log data.
7. Creates the portable ZIP.
8. Uses Inno Setup to create the installer.

## Outputs

```text
release/
├── DSCode Assistant Setup v0.6.0.exe
├── DSCode Assistant v0.6.0 Portable.zip
└── v0.6.0/
    └── portable/
        ├── DSCode Assistant.exe
        ├── LICENSE.txt
        ├── Windows_User_Guide.md
        └── _internal/
```

## Data and credential paths

- Settings: `%APPDATA%\DSCodeAssistant\settings.json`
- SQLite history: `%APPDATA%\DSCodeAssistant\dscode_assistant.db`
- Startup diagnostics: local diagnostic files under `%APPDATA%\DSCodeAssistant`
- API keys: Windows Credential Manager through the Windows keyring backend

The installed and portable application use the same per-user data directory for upgrade compatibility. Neither package stores API keys in its application directory.

## Pre-release verification

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m compileall -q dscode_assistant tests
python -m pytest -q
```

Also verify portable startup and shutdown, first-run data-directory creation, icons and QSS, Markdown resources, Windows Credential Manager access, installer shortcuts, uninstall behavior, and absence of user data in the release directory.

## Notes

- Current open-source builds are not code-signed, so Windows SmartScreen may show an unknown-publisher warning.
- The script cleans temporary build directories and current-version outputs only; it does not delete older release packages.
- The uninstaller preserves `%APPDATA%\DSCodeAssistant` by default to avoid deleting conversation history and settings.
