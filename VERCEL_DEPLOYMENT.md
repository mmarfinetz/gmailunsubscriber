# Gmail Unsubscriber - Vercel Deployment Fix Guide

## Changes Made to Fix Deployment Issues

### 1. Frontend Configuration Updates
- Updated `app.js` to use the hardcoded backend URL instead of relying on environment variables
- This ensures the frontend properly connects to the backend regardless of environment

### 2. Backend CORS Configuration
- Enhanced CORS configuration to specifically allow the frontend domain
- Added explicit headers and methods for cross-origin requests
- Added CORS headers to the Vercel.json configuration

### 3. Session Handling Improvements
- Updated session configuration to work in a serverless environment:
  - Set sessions to be permanent
  - Configured cookie security settings for cross-site requests
  - Set SameSite=None to allow third-party cookies

### 4. Redirect URL Update
- Updated the OAuth callback redirect to use the correct frontend URL

## Required Actions in Vercel Dashboard

1. **Production Environment Variables**
   - Log into the Vercel dashboard at https://vercel.com
   - Navigate to your `gmail-unsubscriber-backend` project
   - Go to Settings > Environment Variables
   - Add the following environment variables to the Production environment:
     - `SECRET_KEY`: A secure random string
     - `GOOGLE_CLIENT_ID`: Your Google Client ID
     - `GOOGLE_CLIENT_SECRET`: Your Google Client Secret
     - `GOOGLE_PROJECT_ID`: Your Google Project ID
     - `REDIRECT_URI`: `https://gmail-unsubscriber-backend-k2fc6t8lf-mmarfinetzs-projects.vercel.app/oauth2callback`
     - `FRONTEND_URL`: `https://gmail-unsubscriber-frontend-itepckgeq-mmarfinetzs-projects.vercel.app`

2. **Redeploy Application**
   - After setting the environment variables, redeploy from the Vercel dashboard:
     - Navigate to the Deployments tab
     - Select the latest deployment
     - Click the "Redeploy" option

3. **Update Google OAuth Configuration**
   - Go to the Google Cloud Console
   - Navigate to "APIs & Services" > "Credentials"
   - Edit your OAuth client
   - Update the authorized JavaScript origins and redirect URIs:
     - Authorized JavaScript origins:
       - `https://gmail-unsubscriber-frontend-itepckgeq-mmarfinetzs-projects.vercel.app`
     - Authorized redirect URIs:
       - `https://gmail-unsubscriber-backend-k2fc6t8lf-mmarfinetzs-projects.vercel.app/oauth2callback`

## Troubleshooting

If you still experience issues after implementing these changes:

1. **Check Browser Console for CORS Errors**
   - Open the developer tools in your browser
   - Look for CORS-related errors in the console

2. **Verify Environment Variables**
   - Ensure all environment variables are correctly set in Vercel
   - Check that they are available in the Production environment

3. **Inspect Network Requests**
   - Use the Network tab in browser developer tools
   - Check the response headers for CORS-related issues

4. **Session Issues**
   - If authentication still fails, you may need to implement a different session storage solution
   - Consider using JWT tokens instead of cookie-based sessions for a serverless environment