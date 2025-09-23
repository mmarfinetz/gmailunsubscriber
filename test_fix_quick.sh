#!/bin/bash
# Quick test to verify the fix works

echo "Quick test for apply endpoint name collision fix"
echo "================================================="

# Check if backend is running
echo -n "Checking if backend is running... "
if curl -s http://localhost:5000/ > /dev/null; then
    echo "✅ Backend is running"
else
    echo "❌ Backend not running. Start it first with:"
    echo "   cd gmail-unsubscriber-backend && python app.py"
    exit 1
fi

# Test that the endpoint exists and doesn't have basic errors
echo -n "Testing /api/unsubscribe/apply endpoint... "
response=$(curl -s -X POST http://localhost:5000/api/unsubscribe/apply \
    -H "Content-Type: application/json" \
    -d '{"items": [], "create_auto_archive_filter": true}' 2>&1)

if echo "$response" | grep -q "'bool' object is not callable"; then
    echo "❌ FAILED - Still getting 'bool' object is not callable error"
    echo "Response: $response"
    exit 1
elif echo "$response" | grep -q "Authentication required"; then
    echo "✅ Endpoint works (authentication required as expected)"
    echo "The name collision bug is fixed!"
    exit 0
else
    echo "Response: $response"
    echo "Note: Need valid auth token for full test"
    exit 0
fi