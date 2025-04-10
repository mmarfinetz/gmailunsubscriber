# Gmail Unsubscriber - Development Guidelines

## Build & Run Commands
- Backend: `cd gmail-unsubscriber-backend && python app.py`
- Frontend: `cd gmail-unsubscriber && python -m http.server 8000`
- API Testing: `curl -v http://localhost:5000/api/auth/status`

## Environment Setup
- Backend dependencies: `pip install -r gmail-unsubscriber-backend/requirements.txt`
- Create `.env` file with Google OAuth credentials (see README.md)

## Code Style Guidelines
- **Python**: PEP 8 compliant with Google docstring format
- **JavaScript**: ES6 syntax with camelCase naming
- **HTML/CSS**: BEM methodology for class naming
- **Error Handling**: Use try/except blocks with detailed logging
- **Imports**: Group standard library, third-party, and local imports
- **Logging**: Use logging module with appropriate levels (INFO, WARNING, ERROR)
- **Types**: Use type hints in Python where appropriate
- **Formatting**: 4 spaces for Python, 2 spaces for JS/HTML/CSS

## Architecture
- Backend: Flask REST API with Google OAuth
- Frontend: Vanilla JavaScript with HTTP server
- Communication: JSON over HTTP with fetch API