# Быстрый старт

## Установка

```bash
git clone https://github.com/RomPl/ssh-mcp-server.git
cd ssh-mcp-server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Настройка `.env`

```bash
cp .env.example .env
chmod 600 .env
```

Минимум для HTTP режима:
- `PUBLIC_BASE_URL=https://<ваш-домен>`
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `ALLOWED_EMAIL`
- `JWT_SECRET`, `SESSION_SECRET`, `OAUTH_CODE_SECRET`

## Запуск

### HTTP/SSE сервер
```bash
source .venv/bin/activate
python server_http.py
```

Проверка:
```bash
curl http://127.0.0.1:3003/health
curl http://127.0.0.1:3003/openapi.json
```

### stdio сервер (Claude Desktop)
```bash
source .venv/bin/activate
python server_stdio.py
```

## Подключение клиентов

### ChatGPT MCP (SSE)
- URL: `https://<ваш-домен>/sse`
- OAuth 2.1 через Google

### Custom GPT Actions (REST)
- OpenAPI schema: `https://<ваш-домен>/openapi.json`
- OAuth:
  - Authorization URL: `https://<ваш-домен>/authorize`
  - Token URL: `https://<ваш-домен>/token`
  - Scope: `mcp`

Если используете static client `chatgpt` без PKCE, задайте `CHATGPT_CLIENT_ID/SECRET/REDIRECT_URI` в `.env`.
