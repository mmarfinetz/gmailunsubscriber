# Claude Code Configuration for Gmail Unsubscriber

This directory contains Claude Code configuration files optimized for Gmail unsubscriber development.

## Files Overview

### `settings.json` (Shared Configuration)
Project-wide settings shared with the team. Contains:
- **Permissions**: Allowed/denied operations for development workflow
- **Environment Variables**: Development environment setup
- **Security**: Protection for sensitive files (`.env`, OAuth secrets)

### `settings.local.json` (Personal Configuration)
Personal development preferences not checked into source control. Contains:
- **Debug Settings**: Enhanced logging and debugging tools
- **Process Management**: Local development utilities
- **External Resources**: API documentation access

### `hooks.json` (Automation)
Automated code quality and validation hooks:
- **Post-Edit**: Auto-formatting with Black and isort, linting with flake8
- **Pre-Write**: Backup sensitive files, detect secrets
- **Post-Bash**: Log deployment commands

### `dev-shortcuts.md` (Quick Reference)
Development command reference for common tasks.

## Key Features

### 🔒 Security Protection
- **Blocked Operations**: Write/Edit access to `.env` and OAuth secret files
- **Secret Detection**: Warns when files may contain sensitive data
- **Backup Creation**: Automatic backups before modifying environment files

### 🚀 Development Workflow
- **Server Management**: Quick start/stop for backend and frontend
- **Testing**: API connectivity and OAuth debugging
- **Deployment**: Vercel, Railway, and Heroku deployment commands
- **Code Quality**: Automated formatting and linting

### 🛠 Tool Permissions
**Allowed Operations:**
- Read/Write/Edit: Python, JavaScript, HTML, CSS, JSON, Markdown files
- Bash: Development servers, testing, git operations, package management
- WebFetch: Official documentation (Google, Vercel, Railway)

**Blocked Operations:**
- Write/Edit: Environment and OAuth secret files
- Bash: Destructive operations (`rm -rf`, `sudo`)
- WebFetch: Potentially unsafe script execution

### 📁 Directory Access
- Full access to `gmail-unsubscriber/` (frontend)
- Full access to `gmail-unsubscriber-backend/` (backend)
- Project root for configuration and documentation

## Environment Variables

### Development Environment
```bash
PYTHONPATH=./gmail-unsubscriber-backend:./
FLASK_ENV=development
FLASK_DEBUG=1
CLAUDE_CODE_PROJECT_TYPE=gmail_unsubscriber
```

### Claude Code Specific
```bash
CLAUDE_CODE_MAX_OUTPUT_TOKENS=8192
BASH_DEFAULT_TIMEOUT_MS=30000
BASH_MAX_TIMEOUT_MS=120000
CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR=true
```

## Usage Examples

### Start Development Environment
```bash
# Claude Code will execute these with proper permissions
cd gmail-unsubscriber-backend && python app.py
cd gmail-unsubscriber && python -m http.server 8000
./test_api.sh
```

### Code Quality Operations
```bash
# Auto-formatting (triggered by hooks)
black --line-length 88 app.py
isort app.py
flake8 --max-line-length=88 app.py
```

### Deployment Commands
```bash
vercel deploy
railway deploy
heroku logs --tail
```

## Troubleshooting

### Permission Issues
If Claude Code blocks an operation you need:
1. Check if it's listed in `settings.json` deny rules
2. Add specific permission to `settings.local.json` for personal use
3. Update `settings.json` for team-wide access

### Hook Failures
If code formatting hooks fail:
1. Install required tools: `pip install black isort flake8`
2. Check Python virtual environment is activated
3. Verify file permissions

### Environment Variables
If environment variables aren't working:
1. Restart Claude Code session
2. Check `settings.json` env configuration
3. Verify virtual environment setup

## Customization

### Personal Settings
Add to `settings.local.json`:
```json
{
  "permissions": {
    "allow": ["Bash(your-custom-command)"]
  },
  "env": {
    "YOUR_CUSTOM_VAR": "value"
  }
}
```

### Team Settings
Modify `settings.json` and commit changes for team-wide updates.

### Additional Hooks
Add to `hooks.json`:
```json
{
  "postEdit": [
    {
      "name": "custom_hook",
      "pattern": "*.py",
      "command": "your-command {file}",
      "description": "Your custom description"
    }
  ]
}
```

## Project Context

This configuration is specifically designed for the Gmail Unsubscriber project:
- **Architecture**: Flask backend + vanilla JavaScript frontend
- **Authentication**: Google OAuth 2.0 with JWT tokens
- **Deployment**: Multi-platform (Vercel, Railway, Heroku)
- **Development**: Local development with testing utilities
- **Security**: OAuth secrets and environment protection

## Related Documentation

- [`../CLAUDE.md`](../CLAUDE.md) - Complete development guidelines
- [`../gmail-unsubscriber-backend/API_DOCS.md`](../gmail-unsubscriber-backend/API_DOCS.md) - API documentation
- [`../gmail-unsubscriber-backend/DEPLOYMENT.md`](../gmail-unsubscriber-backend/DEPLOYMENT.md) - Deployment procedures
- [`../gmail-unsubscriber-backend/USER_GUIDE.md`](../gmail-unsubscriber-backend/USER_GUIDE.md) - User workflow guide 