# Changelog

Формат: Keep a Changelog. Семантическое версионирование: SemVer.

## [Unreleased] - 2026-03-29

### Added
- REST API для Custom GPT Actions: `POST /shell`, `POST /tool/{name}`, `GET /openapi.json`.
- Static OAuth client `chatgpt` (через env) с возможностью authorization code flow без обязательного PKCE.

### Changed
- Устойчивость SSH пула: активная проверка живости соединения, keepalive, одноразовый retry для SSH/SFTP.

## [2.0.0] - 2026-03-25

### Added
- OAuth 2.1 через Google (как Identity Provider)
- Ограничение доступа по `ALLOWED_EMAIL`
- PKCE (S256) для OAuth flow (для не-static клиентов)
- HTTP/SSE transport для ChatGPT MCP
- Dynamic Client Registration

## [1.0.0] - 2026-03-01

### Added
- stdio transport для Claude Desktop
- базовые SSH инструменты (execute/read/write/list)
