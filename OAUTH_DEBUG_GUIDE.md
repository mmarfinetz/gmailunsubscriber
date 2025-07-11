# OAuth Authentication Debug Guide

## Quick Start for Local Development

1. **Copy environment configuration**:
   ```bash
   cd gmail-unsubscriber-backend
   cp .env.local .env
   # Edit .env and add your Google OAuth credentials
   ```

2. **Start the backend**:
   ```bash
   cd gmail-unsubscriber-backend
   python app.py
   ```

3. **Start the frontend**:
   ```bash
   cd gmail-unsubscriber
   python -m http.server 8000
   ```

4. **Run debug script**:
   ```bash
   python debug_oauth.py
   ```

## Common OAuth Issues and Solutions

### Issue 1: InsecureTransportError during OAuth callback

**Error Message**:
```
http://localhost:8000/?auth=error&error=callback_failed&details=InsecureTransportError
```

**Cause**:
Google's OAuth2 requires HTTPS for security, but local development typically runs on HTTP. The `oauthlib` library enforces this security requirement by default.

**Solution**:
The app automatically enables insecure transport for local development by setting `OAUTHLIB_INSECURE_TRANSPORT=1` when:
- `ENVIRONMENT` is set to `development`
- OR when `FRONTEND_URL` starts with `http://localhost`

**Security Warning**:
⚠️ NEVER enable `OAUTHLIB_INSECURE_TRANSPORT` in production! This is only for local development.

**Manual Override** (if needed):
```bash
export ENVIRONMENT=development
# OR
export OAUTHLIB_INSECURE_TRANSPORT=1
```

### Issue 2: "User returns to initial page without being logged in"

**Symptoms**:
- User completes Google OAuth
- Returns to the app but isn't logged in
- No error messages displayed

**Root Causes**:
1. Session state not persisting between requests
2. Environment configuration mismatch
3. CORS blocking requests
4. JWT token not being stored/sent correctly

**Solutions Applied**:
1. ✅ Added Flask session configuration for proper cookie handling
2. ✅ Moved OAuth state from in-memory storage to Flask sessions
3. ✅ Added localhost to CORS allowed origins
4. ✅ Enhanced logging throughout OAuth flow
5. ✅ Added frontend debugging for token storage

### Issue 2: "redirect_uri_mismatch"

**Cause**: The redirect URI in your app doesn't match Google Console

**Solution**:
1. Check your `.env` file: `REDIRECT_URI=http://localhost:5000/oauth2callback`
2. Go to Google Cloud Console → APIs & Services → Credentials
3. Edit your OAuth 2.0 Client ID
4. Add to Authorized redirect URIs:
   - `http://localhost:5000/oauth2callback` (for local dev)
   - Your production URL (for deployment)

### Issue 3: "State validation failed"

**Cause**: Session cookies not persisting across OAuth redirect

**Solution**:
1. Check Flask session configuration (already added)
2. Ensure `SESSION_COOKIE_SAMESITE='Lax'` is set
3. For local dev, ensure `SESSION_COOKIE_SECURE=False`

## Debugging Steps

### 1. Backend OAuth Debug Logs

When you start the backend, you'll see detailed OAuth logs:

```
=== OAuth Login Started ===
Generated OAuth state: abc123...
Stored state in session: abc123...
Authorization URL: https://accounts.google.com/o/oauth2/auth?...
=== OAuth Login Completed ===
```

### 2. Frontend Console Logs

Open browser DevTools (F12) and check Console:

```
=== Checking Auth Status ===
Token present: false
=== OAuth Callback Check ===
URL params: {authStatus: 'success', email: 'present', token: 'present'}
OAuth authentication successful
Token stored in localStorage
```

### 3. Network Tab Analysis

In DevTools Network tab, verify:
1. `/api/auth/login` returns 200 with auth_url
2. OAuth redirect includes state parameter
3. `/oauth2callback` processes successfully
4. Frontend receives token in URL params
5. `/api/auth/status` confirms authentication

### 4. Session Cookie Inspection

In DevTools Application tab:
1. Check Cookies for localhost:5000
2. Verify session cookie exists
3. Check SameSite and Secure attributes
4. Ensure HttpOnly is set

## Testing Checklist

- [ ] Environment variables set correctly in `.env`
- [ ] Backend running on http://localhost:5000
- [ ] Frontend running on http://localhost:8000
- [ ] Google OAuth credentials are valid
- [ ] Redirect URI matches in Google Console
- [ ] No browser extensions blocking cookies
- [ ] Browser allows third-party cookies (for development)

## Environment Variables Reference

```env
# Local Development (.env)
SECRET_KEY=your_secret_key_here
ENVIRONMENT=development
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_PROJECT_ID=your_project_id
REDIRECT_URI=http://localhost:5000/oauth2callback
FRONTEND_URL=http://localhost:8000
JWT_SECRET_KEY=your_jwt_secret
```

## Monitoring OAuth Flow

1. **Start with verbose logging**:
   ```bash
   cd gmail-unsubscriber-backend
   export FLASK_ENV=development
   export FLASK_DEBUG=1
   python app.py
   ```

2. **Watch backend logs** in one terminal
3. **Watch browser console** in DevTools
4. **Use debug script** to verify configuration:
   ```bash
   python debug_oauth.py
   ```

## If All Else Fails

1. Clear browser cookies and localStorage
2. Try incognito/private browsing mode
3. Check for proxy or VPN interference
4. Verify system time is correct
5. Test with a different Google account
6. Check Google account security settings

## Production Deployment Notes

When deploying to production:
1. Set `SESSION_COOKIE_SECURE=True`
2. Update all URLs to HTTPS
3. Add production domain to Google Console
4. Set `ENVIRONMENT=production` in environment variables
5. Use strong secret keys