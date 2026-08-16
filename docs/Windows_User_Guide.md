# DSCode Assistant Windows User Guide

[简体中文](Windows_User_Guide.zh-CN.md)

## Installer package

1. Run `DSCode Assistant Setup v0.6.0.exe`.
2. Choose an installation directory.
3. Optionally enable the desktop shortcut.
4. Start `DSCode Assistant` from the desktop or Start menu.
5. Open Settings on first launch and configure a model provider and API key.

Users do not need to install Python separately.

## Portable package

1. Extract `DSCode Assistant v0.6.0 Portable.zip` to a regular folder.
2. Do not run the application from inside the ZIP archive.
3. Run `DSCode Assistant.exe`.

Portable means that the application does not require installation. Settings and conversation history still use the current Windows user's application-data directory.

## User data and privacy

- Settings and conversation history: `%APPDATA%\DSCodeAssistant`
- API keys: Windows Credential Manager
- DSCode Assistant has no developer-operated relay server. Cloud-model requests go directly to the model-service address selected by the user.

Do not place API keys in project files, screenshots, conversation history, or public Issues.

## Uninstall

Use either:

- Windows **Settings → Apps → Installed apps**
- `Uninstall DSCode Assistant` in the Start menu

The uninstaller preserves `%APPDATA%\DSCodeAssistant` by default to prevent data loss. To remove everything, first confirm that conversation history and settings are no longer needed, then delete that directory manually. Remove stored API keys separately through Windows Credential Manager or the application's Settings page.

## Frequently asked questions

### Windows shows an unknown publisher

Current open-source builds do not use a commercial code-signing certificate. Download packages only from the official project release page or another trusted distribution channel, and verify the filename and version.

### The application cannot save an API key

Confirm that Windows Credential Manager is available, then restart the application as the current Windows user. API keys are not written to `settings.json`.

### Do installed and portable packages share history?

Yes. Both use `%APPDATA%\DSCodeAssistant` by default to preserve upgrade compatibility.
