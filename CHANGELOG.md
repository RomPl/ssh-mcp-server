# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-03-25

### Added
- 🔐 **OAuth 2.1 Authentication** with Google as identity provider
- 🎯 **Email Whitelist** - restrict access to specific users
- 🔑 **PKCE Flow** - secure authorization code exchange
- 📡 **HTTP/SSE Transport** - support for ChatGPT integration
- 🛠️ **File Editing Tool** (`ssh_edit_file`) - replace, insert, delete operations
- 📊 **System Info Tool** (`ssh_system_info`) - CPU, RAM, disk, uptime
- 🔒 **JWT Access Tokens** - HS256 signed, 1-hour expiration
- 🌐 **OAuth Discovery Endpoints** - MCP OAuth 2.1 compliance
- 📝 **Dynamic Client Registration** - automatic client credentials
- 🚀 **Systemd Service Support** - production deployment ready
- 📚 **Comprehensive Documentation** - README, CONTRIBUTING, SECURITY

### Changed
- ♻️ Restructured `.env` configuration with logical grouping
- 📦 Updated `.env.example` with detailed comments and instructions
- 🎨 Improved logging format and output
- 🔧 Enhanced error handling and user feedback

### Security
- 🔐 File permissions enforcement on `.env` (600)
- 🛡️ HMAC-signed authorization codes (stateless)
- ✅ Token validation on every request
- 🚫 Email-based access control
- 🔒 Secure session management

### Fixed
- 🐛 Connection pooling edge cases
- 📝 SFTP file handling improvements
- ⚡ SSE heartbeat timeout issues

## [1.0.0] - 2026-03-01

### Added
- 🎉 Initial release
- 📡 stdio transport for Claude Desktop
- 🔧 Basic SSH tools (execute, read, write, list)
- 🔑 SSH key-based authentication
- 🔌 Paramiko integration
- 📦 Connection pooling

---

[2.0.0]: https://github.com/yourusername/ssh-mcp-server/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/yourusername/ssh-mcp-server/releases/tag/v1.0.0
