# OAuth Authentication Troubleshooting Log

## Overview
This document chronicles the OAuth authentication issues encountered in the Gmail Unsubscriber application and the solutions implemented to resolve them.

## Issues Encountered

### 1. Session State Loss ("no_stored_state" Error)

**Symptoms:**
- User completes Google OAuth sign-in
- Redirected back to app with error: `http://localhost:8000/?auth=error&error=no_stored_state`
- User not logged in despite successful Google authentication

**Root Cause:**
- OAuth state stored in Flask session during `/api/auth/login` was not available during `/oauth2callback`
- Session cookie not persisting between requests

**Attempted Fixes:**
1. **Enhanced Debug Logging** (✅ Implemented)
   ```python
   # Added comprehensive session tracking
   oauth_logger.debug(f"Session before login: {dict(session)}")
   oauth_logger.debug(f"Session ID (if available): {request.cookies.get('session', 'No session cookie')}")
   ```

2. **Frontend Cookie Handling** (✅ Implemented)
   ```javascript
   // Updated all fetch calls to include credentials
   fetch(`${API_BASE_URL}/api/auth/login`, {
       credentials: 'include',
       headers: {
           'Content-Type': 'application/json'
       }
   })
   ```

3. **Session Configuration Updates** (✅ Implemented)
   ```python
   app.config.update(
       SESSION_COOKIE_SECURE=False,
       SESSION_COOKIE_HTTPONLY=True,
       SESSION_COOKIE_SAMESITE='Lax',
       PERMANENT_SESSION_LIFETIME=timedelta(hours=1),
       SESSION_COOKIE_NAME='gmail_unsubscriber_session',
       SESSION_COOKIE_PATH='/'
   )
   ```

4. **Debug Endpoint** (✅ Implemented)
   - Added `/api/session/debug` to inspect session state and configuration

### 2. InsecureTransportError

**Symptoms:**
- OAuth callback fails with: `http://localhost:8000/?auth=error&error=callback_failed&details=InsecureTransportError`
- CSP violation reports sent to Google

**Root Cause:**
- Google OAuth2 requires HTTPS for security
- Local development environment uses HTTP
- `oauthlib` enforces HTTPS requirement by default

**Implemented Solution:**
```python
# Conditionally enable insecure transport for development only
if os.environ.get('ENVIRONMENT') == 'development' or (
    os.environ.get('ENVIRONMENT') is None and 
    os.environ.get('FRONTEND_URL', '').startswith('http://localhost')
):
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    print("WARNING: Running in development mode with OAUTHLIB_INSECURE_TRANSPORT enabled.")
```

### 3. IPv6 Localhost Session Issues

**Symptoms:**
- Session state loss when accessing frontend via `http://[::]:8000/`
- "no_stored_state" error persists despite other fixes

**Root Cause:**
- Python's HTTP server binds to IPv6 by default (`::`)
- Browsers treat `[::]:8000`, `localhost:8000`, and `127.0.0.1:8000` as different domains
- Session cookies set on one domain aren't available on others

**Implemented Solutions:**

1. **Redirect URI Normalization** (✅ Implemented)
   ```python
   # Force consistent localhost usage for local development
   if host in ['[::1]:5000', '[::]:5000', '127.0.0.1:5000'] or 'localhost' in host:
       host = 'localhost:5000'
   ```

2. **Frontend API URL Detection** (✅ Implemented)
   ```javascript
   const API_BASE_URL = window.VITE_API_URL || window.NEXT_PUBLIC_API_BASE_URL || 
       (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || 
        window.location.hostname === '::1' || window.location.hostname.match(/^\[.*\]$/) ? 
        'http://localhost:5000' : 'https://gmailunsubscriber-production.up.railway.app');
   ```

3. **Startup Script** (✅ Implemented)
   - Created `start_local.sh` to ensure consistent localhost binding
   - Forces frontend to bind to 127.0.0.1 instead of IPv6

## Test Tools Created

1. **OAuth Session Test Script** (`test_oauth_session.sh`)
   - Tests session persistence across OAuth flow
   - Captures cookies and session state

2. **Session Debug Page** (`test_session.html`)
   - Interactive session testing
   - Direct API endpoint testing

3. **OAuth Debug Script** (`debug_oauth.py`)
   - Comprehensive OAuth flow testing
   - Detailed error reporting

## Current Status

✅ **Resolved Issues:**
- Session state now persists correctly when using `http://localhost:8000`
- InsecureTransportError resolved for local development
- Debug logging provides comprehensive troubleshooting information

⚠️ **Known Limitations:**
- Must access application via `http://localhost:8000` (not IPv6 URLs)
- OAUTHLIB_INSECURE_TRANSPORT only enabled for development
- Session cookies require proper domain matching

## Recommended Usage

For local development:
```bash
# Use the startup script
./start_local.sh

# Access the application at
http://localhost:8000

# Do NOT use:
# http://[::]:8000
# http://[::1]:8000
```

## Security Considerations

1. **NEVER** enable `OAUTHLIB_INSECURE_TRANSPORT` in production
2. Always use HTTPS for production OAuth flows
3. Session cookies should have `Secure` flag in production
4. Regularly rotate `SECRET_KEY` and `JWT_SECRET_KEY`

## Future Improvements

1. Consider using Redis or similar for session storage in production
2. Implement proper HTTPS for local development using self-signed certificates
3. Add session timeout handling
4. Implement PKCE (Proof Key for Code Exchange) for enhanced OAuth security