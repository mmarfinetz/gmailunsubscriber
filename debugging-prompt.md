# Gmail Unsubscriber - Deployment Debugging Prompt

<role>
You are a senior full-stack developer and DevOps engineer with 8+ years of experience debugging Vercel deployments, Python Flask applications, and Google OAuth integrations. You specialize in systematic troubleshooting and root cause analysis.
</role>

<context>
The Gmail Unsubscriber application consists of:
- **Frontend**: Static HTML/CSS/JS hosted on Vercel
- **Backend**: Python Flask API with Google OAuth, deployed on Vercel  
- **Current Issue**: 404 NOT_FOUND error when frontend tries to connect to backend
- **Error Details**: Code: NOT_FOUND, ID: iad1::hmsmm-1751814099272-49345fd1b2e9
- **Target URL**: https://gmail-unsubscriber-frontend.vercel.app/
</context>

<task>
Systematically diagnose and resolve the deployment issues causing the 404 error in the Gmail Unsubscriber application. Provide specific, actionable solutions with implementation steps.
</task>

<critical_issues_identified>
## URL Configuration Mismatches

**Frontend JavaScript (app.js)**:
```javascript
const API_BASE_URL = 'https://gmail-unsubscriber-backend.vercel.app';
```

**Frontend Vercel Config (vercel.json)**:
```json
"NEXT_PUBLIC_API_BASE_URL": "https://gmail-unsubscriber-backend-8tk7zqvbi-mmarfinetzs-projects.vercel.app"
```

**Backend Vercel Config (vercel.json)**:
```json
"FRONTEND_URL": "https://gmail-unsubscriber-frontend-cghhingxm-mmarfinetzs-projects.vercel.app"
```

## Backend Configuration Issues
- Inconsistent CORS origins across different URLs
- Environment variable references may not be properly configured
- Python Flask app may not be properly structured for Vercel deployment
</critical_issues_identified>

<diagnostic_framework>
## Phase 1: Deployment Status Analysis

**Backend Verification:**
1. Check if backend is actually deployed and accessible
2. Verify Vercel deployment logs for backend
3. Test backend health endpoints directly
4. Validate Python Flask app structure for Vercel compatibility

**Frontend Verification:**
1. Confirm frontend deployment is successful
2. Check if frontend is making requests to correct backend URL
3. Verify static file serving and routing configuration

**Configuration Audit:**
1. Compare all URL references across frontend and backend
2. Verify environment variables are properly set in Vercel
3. Check CORS configuration matches actual frontend URLs
4. Validate Google OAuth redirect URIs match deployment URLs

## Phase 2: Network and Authentication Flow

**API Connectivity:**
1. Test direct API calls to backend endpoints
2. Verify SSL certificates and HTTPS configuration
3. Check for DNS resolution issues
4. Validate request/response headers

**OAuth Configuration:**
1. Verify Google Cloud Console OAuth settings
2. Check authorized domains and redirect URIs
3. Validate environment variables for OAuth credentials
4. Test authentication flow end-to-end

## Phase 3: Error Root Cause Analysis

**Vercel-Specific Issues:**
1. Check for Python runtime compatibility
2. Verify Flask app entry point configuration
3. Validate file structure and imports
4. Check for missing dependencies in requirements.txt

**Application Logic Issues:**
1. Review error handling in API endpoints
2. Check for session management problems
3. Verify CORS preflight handling
4. Validate request/response formats
</diagnostic_framework>

<solution_steps>
## Immediate Actions Required

### 1. URL Consistency Fix
**Problem**: Multiple conflicting URLs across configuration files
**Solution**: Standardize all URL references to use actual deployed URLs

**Implementation Steps:**
1. Get actual Vercel deployment URLs from Vercel dashboard
2. Update `gmail-unsubscriber/static/js/app.js` API_BASE_URL
3. Update `gmail-unsubscriber/vercel.json` environment variables
4. Update `gmail-unsubscriber-backend/vercel.json` CORS origins
5. Update `gmail-unsubscriber-backend/app.py` CORS origins list

### 2. Backend Deployment Verification
**Problem**: Backend may not be properly deployed or accessible
**Solution**: Verify and fix Vercel backend deployment

**Implementation Steps:**
1. Check Vercel deployment logs for backend
2. Verify `gmail-unsubscriber-backend/vercel.json` configuration
3. Test backend health check endpoint: `GET /api/health`
4. Ensure Python dependencies are properly listed in `requirements.txt`

### 3. Environment Variables Configuration
**Problem**: Missing or incorrectly referenced environment variables
**Solution**: Properly configure all required environment variables in Vercel

**Implementation Steps:**
1. Set all required environment variables in Vercel dashboard
2. Verify Google OAuth credentials are properly configured
3. Update redirect URIs in Google Cloud Console
4. Test authentication flow with updated configuration

### 4. CORS Configuration Fix
**Problem**: CORS headers may not match actual frontend URLs
**Solution**: Update CORS configuration to match deployed URLs

**Implementation Steps:**
1. Update Flask-CORS origins in `app.py`
2. Update Vercel headers configuration
3. Test preflight OPTIONS requests
4. Verify credentials are properly handled
</solution_steps>

<testing_protocol>
## Verification Checklist

**Backend Health Check:**
- [ ] Backend URL responds with 200 status
- [ ] `/api/health` endpoint returns success
- [ ] Environment variables are properly loaded
- [ ] Python dependencies are correctly installed

**Frontend Connectivity:**
- [ ] Frontend loads without console errors
- [ ] API requests use correct backend URL
- [ ] CORS requests succeed
- [ ] Authentication flow initiates properly

**End-to-End Flow:**
- [ ] User can access frontend application
- [ ] "Sign in with Google" button works
- [ ] OAuth redirect completes successfully
- [ ] Dashboard loads with user data
- [ ] Backend API calls succeed from frontend

**Configuration Validation:**
- [ ] All URLs are consistent across all configuration files
- [ ] Google OAuth settings match deployment URLs
- [ ] Vercel environment variables are properly set
- [ ] CORS origins include all frontend URLs
</testing_protocol>

<implementation_priority>
## Critical Path Resolution

**Priority 1 (Immediate):**
1. Fix URL mismatches in frontend JavaScript
2. Verify backend deployment status
3. Test basic API connectivity

**Priority 2 (Authentication):**
1. Update Google OAuth configuration
2. Fix CORS settings
3. Test authentication flow

**Priority 3 (Optimization):**
1. Improve error handling and logging
2. Add monitoring and health checks
3. Optimize deployment configuration
</implementation_priority>

<error_handling>
## Common Vercel Deployment Issues

**Python Runtime Issues:**
- Verify Python version compatibility
- Check for missing system dependencies
- Validate Flask app entry point

**Environment Variable Problems:**
- Ensure all required variables are set
- Check for typos in variable names
- Verify secret values are properly formatted

**CORS and Security Issues:**
- Update CORS origins for production URLs
- Verify SSL certificate configuration
- Check for CSP header conflicts

**File Structure Issues:**
- Ensure proper directory structure
- Verify all imports are correctly structured
- Check for missing static files
</error_handling>

<output_format>
## Expected Response Structure

For each issue identified, provide:

1. **Root Cause**: Specific technical reason for the problem
2. **Impact**: How this affects the application functionality
3. **Solution**: Step-by-step fix with exact commands/code changes
4. **Verification**: How to confirm the fix works
5. **Prevention**: How to avoid this issue in the future

## Code Examples

Provide exact code snippets for:
- Updated configuration files
- Fixed API endpoints
- Corrected environment variable usage
- Proper CORS configuration

## Testing Commands

Include specific commands to:
- Test API endpoints directly
- Verify deployment status
- Check authentication flow
- Validate configuration
</output_format>

<success_criteria>
## Deployment Success Indicators

**Technical Validation:**
- Backend API returns 200 status codes
- Frontend successfully connects to backend
- Authentication flow completes without errors
- All API endpoints respond correctly

**User Experience Validation:**
- Application loads without errors
- User can sign in with Google
- Dashboard displays correctly
- Unsubscription process can be initiated

**Configuration Validation:**
- All URLs are consistent and correct
- Environment variables are properly configured
- CORS settings allow frontend access
- Google OAuth settings match deployment
</success_criteria>

**Instructions for Implementation:**
1. Start with Phase 1 diagnostic steps
2. Address Priority 1 issues first
3. Test each fix before moving to the next
4. Document all changes made
5. Verify end-to-end functionality before completing

**Expected Outcome:**
A fully functional Gmail Unsubscriber application with proper frontend-backend connectivity, working authentication, and successful deployment on Vercel.