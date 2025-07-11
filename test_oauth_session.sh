#!/bin/bash

# Test OAuth session handling for Gmail Unsubscriber

echo "=== Testing OAuth Session Handling ==="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Backend URL
BACKEND_URL="http://localhost:5000"

echo -e "${YELLOW}1. Testing session debug endpoint...${NC}"
curl -s -X GET "$BACKEND_URL/api/session/debug" \
  -H "Origin: http://localhost:8000" \
  --cookie-jar cookies.txt \
  --cookie cookies.txt | jq .

echo ""
echo -e "${YELLOW}2. Testing OAuth login (getting auth URL)...${NC}"
AUTH_RESPONSE=$(curl -s -X GET "$BACKEND_URL/api/auth/login" \
  -H "Origin: http://localhost:8000" \
  --cookie-jar cookies.txt \
  --cookie cookies.txt)

echo "Response: $AUTH_RESPONSE" | jq .

# Extract auth URL
AUTH_URL=$(echo $AUTH_RESPONSE | jq -r '.auth_url')

echo ""
echo -e "${YELLOW}3. Checking session after login...${NC}"
curl -s -X GET "$BACKEND_URL/api/session/debug" \
  -H "Origin: http://localhost:8000" \
  --cookie-jar cookies.txt \
  --cookie cookies.txt | jq .

echo ""
echo -e "${GREEN}OAuth URL generated:${NC}"
echo "$AUTH_URL"

echo ""
echo -e "${GREEN}Session cookie stored in cookies.txt:${NC}"
cat cookies.txt

echo ""
echo -e "${YELLOW}To complete the OAuth flow:${NC}"
echo "1. Open the auth URL in your browser"
echo "2. Complete the Google sign-in"
echo "3. Check the browser console for any errors"
echo "4. Check backend logs for session state information"

# Cleanup
rm -f cookies.txt