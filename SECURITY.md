# Security Policy

## Supported Versions

Currently supported versions with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 2.0.x   | :white_check_mark: |
| < 2.0   | :x:                |

## Reporting a Vulnerability

**Please DO NOT report security vulnerabilities through public GitHub issues.**

Instead, please report them privately via:

1. **GitHub Security Advisories**: Use the "Security" tab in this repository
2. **Email**: Send details to [your-email@example.com]

### What to Include

When reporting a vulnerability, please include:

- Type of vulnerability (e.g., authentication bypass, code injection)
- Full paths of affected source files
- Location of the affected code (tag/branch/commit)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the vulnerability

### Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Fix Timeline**: Depends on severity and complexity

## Security Best Practices

### For Users

1. **Protect Secrets**
   - Never commit `.env` to version control
   - Use strong random values for all secrets
   - Set proper file permissions: `chmod 600 .env`

2. **SSH Keys**
   - Use Ed25519 or RSA 4096-bit keys
   - Protect private keys: `chmod 600 ~/.ssh/id_*`
   - Never share private keys

3. **OAuth Configuration**
   - Restrict `ALLOWED_EMAIL` to your account only
   - Keep Google OAuth credentials confidential
   - Use HTTPS for production deployments

4. **Network Security**
   - Run HTTP server behind reverse proxy (Nginx)
   - Use HTTPS/TLS for all external access
   - Consider firewall rules to restrict access

5. **Command Restrictions**
   - Use `ALLOWED_COMMANDS` to limit available commands
   - Review command execution logs regularly
   - Run server with minimal privileges

### For Developers

1. **Code Security**
   - Validate all user inputs
   - Sanitize commands before execution
   - Use parameterized queries/commands
   - Handle errors securely (no sensitive data in logs)

2. **Dependencies**
   - Keep dependencies up to date
   - Review security advisories regularly
   - Use `pip-audit` or similar tools

3. **Authentication**
   - Never bypass OAuth checks
   - Validate tokens on every request
   - Use short-lived tokens (1 hour default)
   - Implement proper PKCE flow

## Known Security Considerations

### Connection Pooling

- Persistent SSH connections are kept open
- Connections are isolated per credential set
- Use `ssh_close_connection` to explicitly close

### Command Execution

- Commands run with server user's privileges
- No command sandboxing by default
- Use `ALLOWED_COMMANDS` for restrictions

### OAuth Flow

- Authorization codes are stateless (HMAC-signed)
- Codes expire after 5 minutes
- PKCE S256 prevents code interception
- Email whitelist prevents unauthorized access

## Security Updates

Security updates will be:
- Released as patch versions (e.g., 2.0.1)
- Announced in GitHub Security Advisories
- Documented in CHANGELOG.md

## Vulnerability Disclosure Policy

We follow responsible disclosure:

1. Reporter notifies us privately
2. We confirm and investigate
3. We develop and test a fix
4. We release a security update
5. We publish security advisory
6. Reporter receives credit (if desired)

---

**Last Updated**: March 2026
