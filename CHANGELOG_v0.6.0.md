# DSCode Assistant v0.6.0

[简体中文](CHANGELOG_v0.6.0.zh-CN.md)

## Added

- Added local Context Optimization with explicit Raw and Light modes.
- Added deterministic cleanup for empty or invalid placeholder messages, safe duplicate removal, and bounded merging of consecutive short messages.
- Added Context Protection rules for system instructions, the current task, the latest valid assistant response, code blocks, patches, error logs, explicit constraints, and file references.
- Added local token estimates and per-request context-protection statistics in the chat UI.
- Added language-aware hints that strengthen error-log and file-reference protection without changing provider requests.

## Improved

- Preserved the existing `ChatWidget -> ChatWorker -> Provider` flow while inserting local context preparation before worker creation.
- Kept Raw mode message output compatible with the previous request format.
- Kept Context Optimization local and deterministic, without an additional model request or database migration.
- Aligned Windows package metadata and output names with v0.6.0.

## Fixed

- No separate runtime bug fix is claimed by the release-preparation changes.
- Existing context tests verify Raw compatibility, Light idempotence, protection behavior, settings compatibility, and unchanged provider message shape.

## Documentation

- Replaced the primary repository README with an English project overview.
- Added a matching Simplified Chinese README.
- Documented Provider boundaries, Context Optimization behavior, privacy guarantees, installation, configuration, and development workflows.
- Added a Code of Conduct, screenshot contribution guidance, and this release-specific changelog.

## Compatibility notes

- Existing settings without `context_optimization_mode` continue to load with Raw as the default.
- Auto is an experimental placeholder in v0.6.0 and currently behaves as Raw.
- Token values shown by Context Statistics are local estimates, not provider billing usage.
- No database schema migration is required for Context Optimization.
