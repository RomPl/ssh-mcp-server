# SSH MCP Server

<div align="center">

![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![MCP](https://img.shields.io/badge/MCP-2024--11--05-purple.svg)

**Secure SSH access for Claude Desktop and ChatGPT via Model Context Protocol**

[Features](#features) • [Installation](#installation) • [Configuration](#configuration) • [Usage](#usage) • [Security](#security)

</div>

---

## 🚀 Features

- **🔧 SSH Operations**: Execute commands, read/write files, manage directories
- **🔐 OAuth 2.1 Security**: Google authentication with PKCE flow
- **📡 Dual Transport**: stdio (Claude Desktop) + HTTP/SSE (ChatGPT)
- **🔑 Key-based Auth**: Support for Ed25519, RSA, ECDSA keys
- **⚡ Connection Pooling**: Persistent SSH connections for performance
- **🛡️ Email Whitelist**: Restrict access to authorized users only

---

## 🛠️ Available Tools

| Tool | Description |
|------|-------------|
| `ssh_execute` | Execute shell commands on remote server |
| `ssh_read_file` | Read file content via SFTP |
| `ssh_write_file` | Write/create files via SFTP |
| `ssh_edit_file` | Edit files with replace/insert/delete operations |
| `ssh_list_directory` | List directory contents |
| `ssh_system_info` | Get system information (CPU, RAM, disk, uptime) |
| `ssh_close_connection` | Close SSH connection |

---

## 📦 Installation

### Prerequisites

- Python 3.8+
- SSH access to target server
- Google OAuth credentials (for HTTP mode)

### Quick Start

```bash
# Clone repository
git clone https://github.com/yourusername/ssh-mcp-server.git
cd ssh-mcp-server

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env  # Edit with your settings
```

---

## ⚙️ Configuration

### Environment Variables

Edit `.env` file with your settings:

```env
# ── HTTP Server Settings ──────────────────────────────────────
HTTP_PORT=3003
HTTP_HOST=127.0.0.1
PUBLIC_BASE_URL=https://mcp.yourdomain.com

# ── OAuth 2.1 Authentication ──────────────────────────────────
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
ALLOWED_EMAIL=you@example.com

# ── Security Secrets ──────────────────────────────────────────
JWT_SECRET=change-me-to-random-string
SESSION_SECRET=change-me-to-random-string
OAUTH_CODE_SECRET=change-me-to-random-string

# ── SSH Connection ────────────────────────────────────────────
SSH_DEFAULT_HOST=127.0.0.1
SSH_DEFAULT_USER=root
SSH_KEY_PATH=/path/to/.ssh/id_ed25519
```

### Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable "Google+ API"
4. Create OAuth 2.0 credentials (Web application)
5. Add authorized redirect URI: `https://yourdomain.com/google/callback`
6. Copy Client ID and Client Secret to `.env`

---

## 🎯 Usage

### Claude Desktop (stdio mode)

Add to Claude Desktop config:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "ssh": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["/absolute/path/to/ssh-mcp-server/server_stdio.py"],
      "env": {
        "SSH_DEFAULT_HOST": "your-server.com",
        "SSH_DEFAULT_USER": "ubuntu",
        "SSH_KEY_PATH": "/home/you/.ssh/id_ed25519"
      }
    }
  }
}
```

Restart Claude Desktop. Tools will appear in the 🔧 menu.

### ChatGPT (HTTP mode)

#### 1. Start HTTP Server

```bash
source .venv/bin/activate
python server_http.py
# or with custom settings:
python server_http.py --host 0.0.0.0 --port 3003
```

#### 2. Verify Health

```bash
curl http://localhost:3003/health
```

#### 3. Configure ChatGPT

Go to **ChatGPT → GPTs → Configure → Actions → Add MCP Server**

- **URL**: `https://mcp.yourdomain.com/sse`
- **Auth**: OAuth 2.1 (automatic via Google)

---

## 🔒 Security

### Authentication Flow

1. **OAuth 2.1 with PKCE**: Industry-standard authorization
2. **Google Identity Provider**: Leverage Google's secure authentication
3. **Email Whitelist**: Only `ALLOWED_EMAIL` can access the server
4. **JWT Tokens**: Short-lived access tokens (1 hour)
5. **HMAC-signed Codes**: Stateless authorization codes

### Best Practices

✅ **DO**:
- Use SSH key-based authentication
- Set strong random secrets (use `openssl rand -hex 32`)
- Run server behind HTTPS reverse proxy
- Restrict `ALLOWED_EMAIL` to your account only
- Use `ALLOWED_COMMANDS` to limit available commands
- Set proper file permissions on `.env` (600)

❌ **DON'T**:
- Don't use password authentication in production
- Don't expose HTTP server directly to internet
- Don't commit `.env` to git
- Don't share your secrets or OAuth credentials

### File Permissions

```bash
# Secure .env file
chmod 600 .env

# Secure SSH keys
chmod 600 ~/.ssh/id_ed25519
```

---

## 🚀 Production Deployment

### Systemd Service

Create `/etc/systemd/system/ssh-mcp.service`:

```ini
[Unit]
Description=SSH MCP Server (HTTP+SSE)
After=network.target

[Service]
User=youruser
WorkingDirectory=/home/youruser/ssh-mcp-server
ExecStart=/home/youruser/ssh-mcp-server/.venv/bin/python server_http.py
EnvironmentFile=/home/youruser/ssh-mcp-server/.env
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable --now ssh-mcp.service
sudo systemctl status ssh-mcp.service
```

### Nginx Reverse Proxy

```nginx
server {
    listen 443 ssl http2;
    server_name mcp.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/mcp.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mcp.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:3003;
        proxy_http_version 1.1;
        
        # SSE support
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400;
        
        # Headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 📁 Project Structure

```
ssh-mcp-server/
├── server_stdio.py      # stdio transport (Claude Desktop)
├── server_http.py       # HTTP+SSE transport (ChatGPT)
├── auth_oauth.py        # OAuth 2.1 authentication logic
├── tools.py             # MCP tool definitions
├── ssh_client.py        # SSH/SFTP client (Paramiko)
├── requirements.txt     # Python dependencies
├── .env.example         # Example configuration
├── .gitignore          # Git ignore rules
├── LICENSE             # MIT License
└── README.md           # This file
```

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [Model Context Protocol](https://modelcontextprotocol.io/) - MCP specification
- [Anthropic Claude](https://claude.ai/) - Claude Desktop integration
- [OpenAI ChatGPT](https://chatgpt.com/) - ChatGPT integration
- [Paramiko](https://www.paramiko.org/) - Python SSH library

---

## 📞 Support

For issues, questions, or contributions, please [open an issue](https://github.com/yourusername/ssh-mcp-server/issues).

---

<div align="center">

**Made with ❤️ for the MCP community**

</div>
