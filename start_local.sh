#!/bin/bash

echo "=== Starting Gmail Unsubscriber Local Development ==="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if backend is already running
if lsof -i:5000 > /dev/null 2>&1; then
    echo -e "${YELLOW}Backend already running on port 5000${NC}"
else
    echo -e "${GREEN}Starting backend server...${NC}"
    cd gmail-unsubscriber-backend
    python app.py &
    BACKEND_PID=$!
    cd ..
    sleep 2
fi

# Check if frontend is already running
if lsof -i:8000 > /dev/null 2>&1; then
    echo -e "${YELLOW}Frontend already running on port 8000${NC}"
else
    echo -e "${GREEN}Starting frontend server...${NC}"
    cd gmail-unsubscriber
    python -m http.server 8000 --bind 127.0.0.1 &
    FRONTEND_PID=$!
    cd ..
    sleep 2
fi

echo ""
echo -e "${GREEN}Services started successfully!${NC}"
echo ""
echo "Access the application at:"
echo -e "${GREEN}http://localhost:8000${NC} (recommended)"
echo "or"
echo -e "${GREEN}http://127.0.0.1:8000${NC}"
echo ""
echo "Do NOT use http://[::]:8000 as it may cause session issues"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for user to press Ctrl+C
trap 'kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit' INT
wait