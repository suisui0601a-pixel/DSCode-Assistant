# DSCode Assistant User Guide

[简体中文](用户使用说明.md)

## 1. Start the application

On Windows, start DSCode Assistant from the installed shortcut or run `DSCode Assistant.exe` from the extracted portable directory. The first launch creates ordinary settings and the SQLite history database in the local application-data directory.

## 2. Configure a model provider

1. Select **Settings** at the bottom of the sidebar.
2. Choose **DeepSeek** or **OpenAI Compatible**.
3. Enter the model, API key, and applicable parameters.
4. Select **Test connection**.
5. Save after the test succeeds.

The API-key field uses password display mode. Saved keys are managed by the operating-system credential store.

## 3. Configure Context Optimization

- **Raw**: keeps the request messages unchanged.
- **Light**: performs deterministic local cleanup while protecting system instructions, the current task, the latest reply, code, patches, error logs, explicit constraints, and file references.
- **Auto (experimental placeholder)**: currently behaves as Raw.

Token values in the interface are local estimates for comparing the current request before and after preparation. They are not provider billing data. Light does not make an additional model request or semantically summarize or rewrite source code.

## 4. Use conversations

1. Select **New chat**.
2. Optionally choose a programming prompt template.
3. Enter a question and press Enter to send; use Shift+Enter for a new line.
4. Select **Stop** while a response is being generated if needed.
5. Completed conversations are stored in the local database.

## 5. Manage history

- Filter conversations with the sidebar search field.
- Rename a conversation by double-clicking it or using its menu.
- Deletion requires confirmation.
- All history can be cleared from Settings.

Deleted conversations cannot be restored in the application.

## 6. Data location

The default Windows directory is:

```text
%APPDATA%\DSCodeAssistant
```

It normally contains `settings.json`, `dscode_assistant.db`, and privacy-safe diagnostic logs. API keys are stored separately in the operating-system credential store.

## 7. Exit safely

Closing the main window stops active chat threads and closes the local database and localhost Automation interface. When a response is still being generated, use **Stop** before exiting when practical.
