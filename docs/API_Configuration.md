# DSCode Assistant API Configuration

[简体中文](API配置说明.md)

## DeepSeek official API

1. Create a personal API key on the DeepSeek platform.
2. Open DSCode Assistant Settings.
3. Select **DeepSeek**.
4. Enter the API key, model name, Temperature, and Max Tokens.
5. Test the connection and save.

The client uses the following official API base address:

```text
https://api.deepseek.com
```

The DeepSeek API key is not sent to a DSCode-operated server. Requests travel directly from the user's computer to the official DeepSeek API.

## OpenAI-compatible provider

Configure:

- Base URL
- Model Name
- API key, when the endpoint requires authentication
- Temperature
- Max Tokens

Example local endpoint:

```text
http://127.0.0.1:11434/v1
```

Use only trusted endpoints. A remote Base URL receives the conversation context that the user chooses to send and applies its own data-processing policy.

## Credential storage

Provider API keys are stored through Python `keyring` in the operating-system credential store:

- Windows: Windows Credential Manager
- macOS: Keychain
- Linux: an available Secret Service/keyring backend

Do not place API keys in `.env`, source files, tests, `settings.json`, or the database.

## Context Optimization

- **Raw**: preserves the original request messages.
- **Light**: applies deterministic local cleanup and protects critical instructions, code, error logs, and file references.
- **Auto (experimental placeholder)**: currently behaves as Raw in v0.6.0.

Context Optimization does not create an additional API request. Token values displayed by the application are local estimates and may differ from provider usage or billing data.

## Common connection errors

- `401`: missing or invalid API key
- `402`: insufficient account balance or unavailable service
- `404`: unknown Base URL or model name
- `429`: request rate exceeded
- Timeout: check the network, provider status, and timeout setting

Model names, pricing, limits, and availability can change. Consult the selected provider's official documentation.
