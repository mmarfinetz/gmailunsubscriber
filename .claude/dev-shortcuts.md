# Gmail Unsubscriber - Claude Code Development Shortcuts

## Quick Start Commands

### Development Servers
- **Start Backend**: `cd gmail-unsubscriber-backend && python app.py`
- **Start Frontend**: `cd gmail-unsubscriber && python -m http.server 8000`
- **Test API**: `./test_api.sh`

### Local Testing
- **Backend Health**: `curl -v http://localhost:5000/api/auth/status`
- **OAuth Debug**: `python debug_oauth.py`
- **Cache Test**: `python test_claude_cache.py`

### Production Testing
- **Prod Health**: `curl -v https://gmail-unsubscriber-backend.vercel.app/api/auth/status`
- **Vercel Logs**: `vercel logs`
- **Railway Logs**: `railway logs`

### Code Quality
- **Format Python**: `black --line-length 88 *.py`
- **Sort Imports**: `isort *.py`
- **Lint Code**: `flake8 --max-line-length=88 --extend-ignore=E203 *.py`
- **Type Check**: `mypy *.py`

### Git Workflow
- **Status**: `git status`
- **Stage All**: `git add .`
- **Commit**: `git commit -m "feat: description"`
- **Push**: `git push origin feature/branch-name`

### Deployment
- **Vercel Deploy**: `vercel deploy`
- **Railway Deploy**: `railway deploy`
- **Heroku Deploy**: `git push heroku main`

### Debug & Monitoring
- **View Backend Logs**: `tail -f gmail-unsubscriber-backend/backend.log`
- **Check Processes**: `ps aux | grep python`
- **Check Port 5000**: `lsof -i :5000`
- **Check Port 8000**: `lsof -i :8000`

### Environment Setup
- **Create venv**: `python -m venv venv`
- **Activate venv**: `source venv/bin/activate`
- **Install Backend Deps**: `pip install -r gmail-unsubscriber-backend/requirements.txt`
- **Install Vercel Deps**: `pip install -r gmail-unsubscriber-backend/requirements-vercel.txt`

### File Locations
- **Backend API**: `gmail-unsubscriber-backend/app.py`
- **Frontend JS**: `gmail-unsubscriber/static/js/app.js`
- **API Docs**: `gmail-unsubscriber-backend/API_DOCS.md`
- **User Guide**: `gmail-unsubscriber-backend/USER_GUIDE.md`
- **Deployment Guide**: `gmail-unsubscriber-backend/DEPLOYMENT.md`

### Security Files (Protected)
- **Environment**: `.env` (never commit)
- **Client Secrets**: `client_secret*.json` (never commit)
- **Backend Secrets**: `gmail-unsubscriber-backend/client_secrets.json` (never commit)

## Claude Code Specific

### Permission Patterns
- Python files: `*.py` (Read/Write/Edit allowed)
- JavaScript files: `*.js` (Read/Write/Edit allowed)
- Config files: `*.json` (Read/Write/Edit allowed)
- Documentation: `*.md` (Read/Write/Edit allowed)
- Secrets: `*.env*`, `client_secret*.json` (Read only, Write/Edit denied)

### Allowed Commands
- Development servers, testing, git operations
- Package installation, code formatting
- Deployment commands for Vercel/Railway/Heroku
- Log viewing and process monitoring

### Quick Claude Commands
- `/config` - View Claude Code configuration
- `/allowed-tools` - View allowed tools and permissions
- `/bug` - Report issues (if enabled) 