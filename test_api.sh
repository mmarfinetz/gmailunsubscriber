#!/bin/bash

# Test script to verify API connectivity between frontend and backend

echo "🔍 Testing Gmail Unsubscriber API connectivity..."
echo "================================================="

# Backend URL
BACKEND_URL="https://gmailunsubscriber-production.up.railway.app"
FRONTEND_URL="https://gmail-unsubscriber-frontend.vercel.app"

echo "✅ Backend URL: $BACKEND_URL"
echo "✅ Frontend URL: $FRONTEND_URL"
echo ""

# Test 1: Backend health check
echo "1. Testing backend health..."
response=$(curl -s -w "%{http_code}" -o /tmp/api_test.json "$BACKEND_URL/")
http_code="${response: -3}"

if [ "$http_code" = "200" ]; then
    echo "✅ Backend is running"
    echo "   Response: $(cat /tmp/api_test.json)"
else
    echo "❌ Backend health check failed (HTTP $http_code)"
    exit 1
fi

echo ""

# Test 2: CORS test with frontend origin
echo "2. Testing CORS with frontend origin..."
response=$(curl -s -w "%{http_code}" -o /tmp/cors_test.json \
    -H "Origin: $FRONTEND_URL" \
    "$BACKEND_URL/api/auth/status")
http_code="${response: -3}"

if [ "$http_code" = "200" ]; then
    echo "✅ CORS working correctly"
    echo "   Response: $(cat /tmp/cors_test.json)"
else
    echo "❌ CORS test failed (HTTP $http_code)"
    exit 1
fi

echo ""

# Test 3: Check CORS headers
echo "3. Checking CORS headers..."
cors_headers=$(curl -s -I -H "Origin: $FRONTEND_URL" "$BACKEND_URL/api/auth/status" | grep -i "access-control")

if [ -n "$cors_headers" ]; then
    echo "✅ CORS headers present:"
    echo "$cors_headers"
else
    echo "❌ No CORS headers found"
    exit 1
fi

echo ""

# Test 4: Test authentication endpoint
echo "4. Testing authentication endpoint..."
response=$(curl -s -w "%{http_code}" -o /tmp/auth_test.json \
    -H "Origin: $FRONTEND_URL" \
    "$BACKEND_URL/api/auth/login")
http_code="${response: -3}"

if [ "$http_code" = "200" ]; then
    echo "✅ Authentication endpoint working"
    echo "   Response: $(cat /tmp/auth_test.json)"
else
    echo "❌ Authentication endpoint failed (HTTP $http_code)"
    echo "   Error: $(cat /tmp/auth_test.json)"
fi

echo ""

# Test 5: Frontend accessibility
echo "5. Testing frontend accessibility..."
response=$(curl -s -w "%{http_code}" -o /tmp/frontend_test.html "$FRONTEND_URL/")
http_code="${response: -3}"

if [ "$http_code" = "200" ]; then
    echo "✅ Frontend is accessible"
    echo "   Response length: $(wc -c < /tmp/frontend_test.html) bytes"
else
    echo "❌ Frontend not accessible (HTTP $http_code)"
    echo "   Error: $(cat /tmp/frontend_test.html)"
fi

echo ""
echo "🎉 API connectivity test completed!"

# Cleanup
rm -f /tmp/api_test.json /tmp/cors_test.json /tmp/auth_test.json /tmp/frontend_test.html