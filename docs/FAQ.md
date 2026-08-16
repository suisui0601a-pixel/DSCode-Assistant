# DSCode Assistant Frequently Asked Questions

[简体中文](常见问题.md)

## Does DSCode Assistant upload my entire codebase?

No. It does not automatically scan or upload the project directory. Only content that the user sends in the current conversation, together with the conversation context prepared for that request, is transmitted to the selected model provider.

## Where is my API key stored?

In the operating-system credential store. It is not written to ordinary JSON, SQLite, or logs.

## Where is conversation history stored?

In a SQLite database under the local application-data directory. DSCode Assistant has no developer-operated cloud database.

## Why can model API usage cost money?

DSCode Assistant is free and open source, but model providers may charge for API usage. Pricing, credits, and limits are determined by the selected provider account.

## Does Light Context Optimization rewrite code?

No. Light performs deterministic cleanup and bounded short-message merging while protecting code blocks, patches, error logs, constraints, and file references. It does not call another model or semantically summarize code. Displayed Token values are local estimates, not billing records.

## Can I use a local model?

You can connect to a local service that exposes an OpenAI-compatible API. DSCode Assistant does not currently download models, manage model files, or schedule GPU resources.

## Does the Automation interface execute tasks automatically?

No. It listens on `127.0.0.1` and can activate the application, select a project, or prepare a task draft. The user must review and send the task.

## Why can I not copy only the portable EXE?

The PyInstaller onedir package depends on the adjacent `_internal` directory. Extract and keep the complete directory structure.

## How do I remove local data completely?

First clear history and delete API keys from Settings, then uninstall the application. If required, manually delete `%APPDATA%\DSCodeAssistant` after backing up any conversations you need.

## How do I report a problem?

Open a GitHub Issue with the version, operating system, reproduction steps, and sanitized error information. Do not upload API keys, private code, databases, or privacy-sensitive screenshots.
