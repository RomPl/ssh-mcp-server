# Project Files Overview

## 📁 Core Application Files

| File | Description | Public |
|------|-------------|--------|
| `server_http.py` | HTTP/SSE server for ChatGPT integration with OAuth 2.1 | ✅ |
| `server_stdio.py` | stdio server for Claude Desktop integration | ✅ |
| `auth_oauth.py` | OAuth 2.1 authentication logic, JWT tokens, PKCE | ✅ |
| `tools.py` | MCP tool definitions and dispatcher | ✅ |
| `ssh_client.py` | SSH/SFTP client wrapper with connection pooling | ✅ |

## 📝 Documentation Files

| File | Description | Public |
|------|-------------|--------|
| `README.md` | Main documentation with installation & usage | ✅ |
| `CHANGELOG.md` | Version history and release notes | ✅ |
| `CONTRIBUTING.md` | Contribution guidelines | ✅ |
| `SECURITY.md` | Security policy and vulnerability reporting | ✅ |
| `LICENSE` | MIT License | ✅ |
| `PUBLISH.md` | GitHub publication instructions (this can be removed after publishing) | ⚠️ |

## ⚙️ Configuration Files

| File | Description | Public |
|------|-------------|--------|
| `.env.example` | Example environment variables | ✅ |
| `.env` | **ACTUAL secrets - NEVER COMMIT** | ❌ |
| `.gitignore` | Git ignore rules | ✅ |
| `requirements.txt` | Python dependencies | ✅ |

## 🔧 Example Deployment Files

| File | Description | Public |
|------|-------------|--------|
| `ssh-mcp.service.example` | Systemd service template | ✅ |
| `nginx.conf.example` | Nginx reverse proxy configuration | ✅ |

## 📂 Directories

| Directory | Description | Git Status |
|-----------|-------------|------------|
| `.venv/` | Python virtual environment | Ignored |
| `__pycache__/` | Python bytecode cache | Ignored |
| `logs/` | Application logs | Ignored |
| `public_html/` | Web assets (if any) | Ignored |

## 🔐 Security Critical Files

### NEVER commit these:
- `.env` - Contains all secrets and credentials
- Private SSH keys
- `logs/*` - May contain sensitive information
- Any backup files (`*.bak`, `*.backup`)

### Safe to commit:
- `.env.example` - Template with placeholder values
- All `.py` source files
- All `.md` documentation
- `.gitignore`
- `requirements.txt`

## 📊 File Size Summary

```bash
# Source code
server_http.py      ~14KB
auth_oauth.py       ~8KB
ssh_client.py       ~8KB
tools.py            ~15KB
server_stdio.py     ~3KB

# Documentation
README.md           ~12KB
CONTRIBUTING.md     ~3KB
SECURITY.md         ~3KB
CHANGELOG.md        ~2KB

# Total project size (excluding .venv): ~100KB
```

## 🎯 Essential Files Checklist

Before publishing to GitHub, ensure these exist:

- [x] README.md (main documentation)
- [x] LICENSE (MIT)
- [x] .gitignore (with .env excluded)
- [x] .env.example (template)
- [x] requirements.txt
- [x] All .py source files
- [x] CONTRIBUTING.md
- [x] SECURITY.md
- [x] CHANGELOG.md
- [x] Example config files

And ensure these are EXCLUDED:

- [x] .env (actual secrets)
- [x] .venv/ (virtual environment)
- [x] __pycache__/ (Python cache)
- [x] logs/ (application logs)
- [x] *.pyc (compiled Python)

---

**Last Updated**: March 2026
