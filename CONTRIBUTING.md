# Contributing to SSH MCP Server

Thank you for your interest in contributing to SSH MCP Server! This document provides guidelines and instructions for contributing.

## 🤝 How to Contribute

### Reporting Bugs

Before creating bug reports, please check existing issues to avoid duplicates. When creating a bug report, include:

- **Description**: Clear description of the issue
- **Steps to Reproduce**: Detailed steps to reproduce the behavior
- **Expected Behavior**: What you expected to happen
- **Actual Behavior**: What actually happened
- **Environment**: OS, Python version, relevant configuration
- **Logs**: Relevant log output or error messages

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, include:

- **Use Case**: Describe the problem you're trying to solve
- **Proposed Solution**: Your proposed implementation
- **Alternatives**: Any alternative solutions you've considered
- **Additional Context**: Screenshots, mockups, or examples

### Pull Requests

1. **Fork the repository** and create your branch from `main`
2. **Make your changes** following the code style guidelines below
3. **Test your changes** thoroughly
4. **Update documentation** if needed (README, docstrings)
5. **Commit with clear messages** following conventional commits
6. **Open a Pull Request** with a clear description

## 🎨 Code Style Guidelines

### Python Style

- Follow [PEP 8](https://pep8.org/) style guide
- Use type hints where applicable
- Maximum line length: 100 characters
- Use descriptive variable and function names

### Docstrings

Use Google-style docstrings:

```python
def example_function(param1: str, param2: int) -> bool:
    """Brief description of function.
    
    More detailed description if needed.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When invalid input is provided
    """
    pass
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add SSH connection timeout configuration
fix: resolve SFTP file permission issue
docs: update installation instructions
refactor: improve error handling in ssh_client
test: add unit tests for auth_oauth module
```

## 🧪 Testing

Before submitting a PR:

1. Test both stdio and HTTP modes
2. Verify OAuth flow works correctly
3. Test all SSH tools (execute, read, write, etc.)
4. Check error handling and edge cases
5. Ensure no secrets are exposed in logs

## 📝 Documentation

- Update README.md for user-facing changes
- Update docstrings for code changes
- Add examples for new features
- Keep .env.example in sync with .env requirements

## 🔐 Security

- Never commit secrets or credentials
- Use environment variables for sensitive data
- Follow security best practices
- Report security vulnerabilities privately

## 📜 License

By contributing, you agree that your contributions will be licensed under the MIT License.

## ❓ Questions?

Feel free to open an issue for any questions or clarifications.

---

**Thank you for contributing!** 🎉
