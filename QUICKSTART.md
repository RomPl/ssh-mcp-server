# Quick Start Guide

## 🚀 5-Minute Setup

### 1. Install

```bash
git clone https://github.com/YOUR_USERNAME/ssh-mcp-server.git
cd ssh-mcp-server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
nano .env
```

**Minimal required settings:**
```env
# For Claude Desktop (stdio)
SSH_DEFAULT_HOST=your-server.com
SSH_DEFAULT_USER=ubuntu
SSH_KEY_PATH=/home/you/.ssh/id_ed25519

# For ChatGPT (HTTP) - also need:
PUBLIC_BASE_URL=https://mcp.yourdomain.com
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
ALLOWED_EMAIL=you@gmail.com
JWT_SECRET=$(openssl rand -hex 32)
SESSION_SECRET=$(openssl rand -hex 32)
OAUTH_CODE_SECRET=$(openssl rand -hex 32)
```

### 3. Run

**Claude Desktop:**
```bash
python server_stdio.py
```

**ChatGPT:**
```bash
python server_http.py
```

## 📱 Claude Desktop Integration

**Config file location:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

**Add to config:**
```json
{
  "mcpServers": {
    "ssh": {
      "command": "/absolute/path/.venv/bin/python",
      "args": ["/absolute/path/server_stdio.py"]
    }
  }
}
```

Restart Claude Desktop ✅

## 🤖 ChatGPT Integration

### Setup OAuth (one time)

1. Google Cloud Console → Create OAuth Client
2. Add redirect: `https://yourdomain.com/google/callback`
3. Copy credentials to `.env`

### Deploy

```bash
# Start server
python server_http.py

# Or with systemd
sudo cp ssh-mcp.service.example /etc/systemd/system/ssh-mcp.service
sudo systemctl enable --now ssh-mcp
```

### Add to ChatGPT

GPTs → Configure → Actions → Add MCP Server
- URL: `https://mcp.yourdomain.com/sse`

## 🔧 Available Commands

Once connected, you can:

```
# Execute commands
"Run 'df -h' on the server"

# Read files
"Show me /var/log/nginx/access.log"

# Write files
"Create a file /tmp/test.txt with 'Hello World'"

# Edit files
"Replace 'old text' with 'new text' in /etc/config.conf"

# System info
"What's the CPU and RAM usage?"

# List files
"Show files in /var/www"
```

## 🔒 Security Checklist

- [x] `.env` file permissions: `chmod 600 .env`
- [x] SSH key permissions: `chmod 600 ~/.ssh/id_ed25519`
- [x] HTTPS enabled (production)
- [x] Strong random secrets generated
- [x] `ALLOWED_EMAIL` restricted to your account
- [x] Firewall configured (optional)

## ❓ Troubleshooting

**"Connection failed"**
- Check SSH credentials in `.env`
- Verify SSH key path and permissions
- Test manual SSH: `ssh user@host`

**"OAuth error"**
- Verify Google OAuth credentials
- Check redirect URI matches exactly
- Ensure `ALLOWED_EMAIL` is correct

**"Permission denied"**
- Check `.env` file permissions (600)
- Verify user has access to SSH key
- Check server user permissions

## 📚 Full Documentation

- [README.md](README.md) - Complete documentation
- [SECURITY.md](SECURITY.md) - Security guidelines
- [CONTRIBUTING.md](CONTRIBUTING.md) - How to contribute

## 🆘 Support

- Issues: https://github.com/YOUR_USERNAME/ssh-mcp-server/issues
- Discussions: https://github.com/YOUR_USERNAME/ssh-mcp-server/discussions

---

**That's it! You're ready to go! 🎉**
