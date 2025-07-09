#!/bin/bash

echo "=== Railway OAuth Debug Script ==="
echo ""

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "Railway CLI is not installed. Please install it first:"
    echo "brew install railway"
    exit 1
fi

echo "1. Checking recent Railway logs..."
echo "================================="
railway logs --service=web --lines=100 | grep -E "(OAuth|callback|error|Error|ERROR)"

echo ""
echo "2. Testing debug endpoint..."
echo "================================="
curl -s https://gmailunsubscriber-production.up.railway.app/api/debug/env | python3 -m json.tool

echo ""
echo "3. Testing auth status endpoint..."
echo "================================="
curl -s https://gmailunsubscriber-production.up.railway.app/api/auth/status | python3 -m json.tool

echo ""
echo "4. Environment Variables Checklist"
echo "================================="
echo "Please verify these are set in Railway dashboard:"
echo "[ ] SECRET_KEY - Generate with: python3 -c \"import secrets; print(secrets.token_hex(32))\""
echo "[ ] GOOGLE_CLIENT_ID - From Google Cloud Console"
echo "[ ] GOOGLE_CLIENT_SECRET - From Google Cloud Console"
echo "[ ] GOOGLE_PROJECT_ID - From Google Cloud Console"
echo "[ ] REDIRECT_URI = https://gmailunsubscriber-production.up.railway.app/oauth2callback"
echo "[ ] FRONTEND_URL - Your frontend Vercel URL"
echo "[ ] ENVIRONMENT = production"

echo ""
echo "5. Google Cloud Console Checklist"
echo "================================="
echo "[ ] OAuth consent screen is configured"
echo "[ ] https://gmailunsubscriber-production.up.railway.app/oauth2callback is in authorized redirect URIs"
echo "[ ] Gmail API is enabled"
echo "[ ] OAuth 2.0 credentials are created and downloaded"