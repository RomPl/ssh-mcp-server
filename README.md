# SSH MCP Server

Сервер MCP для безопасного доступа к удалённому Linux по SSH.

Поддерживаются два слоя API:
- MCP transport для клиентов (stdio и HTTP/SSE).
- Дополнительный REST API для Custom GPT Actions поверх `tools.py` (без дублирования бизнес‑логики).

## Требования

- Python 3.10+
- SSH доступ к целевому серверу
- Google OAuth credentials (для HTTP режима)

## Возможности

- Выполнение команд и SFTP операции через набор MCP tools (`tools.py`).
- OAuth 2.1 через Google (идентификация) + JWT (доступ к API).
- HTTP/SSE для ChatGPT MCP: `/sse`, `/messages`.
- REST для Custom GPT Actions: `/shell`, `/tool/{name}`, `/openapi.json`.
- Устойчивый SSH пул: keepalive, проверка живости, один retry на сетевые/SSH ошибки.

## Эндпоинты

### Служебные
- `GET /health` — проверка состояния
- `GET /openapi.json` — минимальная OpenAPI 3.1 схема для REST endpoints

### MCP (ChatGPT MCP / SSE)
- `GET /sse` — SSE (требует Bearer token)
- `POST /messages` — JSON-RPC (требует Bearer token)

### REST для Custom GPT Actions
- `POST /shell` — вызывает `t.dispatch("ssh_execute", args)` (требует Bearer token)
- `POST /tool/{name}` — вызывает `t.dispatch(name, arguments)` (требует Bearer token)

## OAuth: модели доступа

По умолчанию (для “обычных” клиентов) действует OAuth 2.1 + PKCE (S256): на `/authorize` нужен `code_challenge`, на `/token` — `code_verifier`.

Для одного static клиента Custom GPT Actions (`client_id=chatgpt`) поддержан authorization code flow без обязательного PKCE:
- включается только при наличии `CHATGPT_CLIENT_ID`, `CHATGPT_CLIENT_SECRET`, `CHATGPT_REDIRECT_URI` в `.env`
- применяется только к `client_id == CHATGPT_CLIENT_ID`
- требует строгого совпадения `redirect_uri` и проверки `client_secret_post`
- для остальных клиентов PKCE остаётся обязательным

## Установка и запуск

См. `QUICKSTART.md`.

## Конфигурация

Скопируйте шаблон и заполните:
```bash
cp .env.example .env
chmod 600 .env
```

Критичные переменные:
- `PUBLIC_BASE_URL` — внешний HTTPS URL сервера (без `/` на конце)
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` — для логина через Google
- `ALLOWED_EMAIL` — единственный разрешённый email
- `JWT_SECRET`, `SESSION_SECRET`, `OAUTH_CODE_SECRET` — длинные случайные секреты
- `SSH_DEFAULT_HOST`, `SSH_DEFAULT_USER` — SSH defaults (если не передаются в tool args)

Для Custom GPT Actions (static `chatgpt`) добавьте:
- `CHATGPT_CLIENT_ID`
- `CHATGPT_CLIENT_SECRET`
- `CHATGPT_REDIRECT_URI`

## Безопасность

Коротко:
- `.env` не коммитить; права `600`.
- Используйте allowlist команд (`ALLOWED_COMMANDS`), если нужно ограничение.
- Доступ к API защищён OAuth + `ALLOWED_EMAIL`.

Подробно: `SECURITY.md`.
