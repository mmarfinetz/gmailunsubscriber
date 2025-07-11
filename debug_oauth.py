#!/usr/bin/env python3
"""
OAuth Debug Script for Gmail Unsubscriber
This script helps debug OAuth authentication issues by testing the flow step by step.
"""

import os
import sys
import requests
import json
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'gmail-unsubscriber-backend'))

# Load environment variables
load_dotenv('gmail-unsubscriber-backend/.env')

def check_environment():
    """Check if all required environment variables are set."""
    print("=== Environment Check ===")
    required_vars = [
        'GOOGLE_CLIENT_ID',
        'GOOGLE_CLIENT_SECRET',
        'GOOGLE_PROJECT_ID',
        'SECRET_KEY',
        'REDIRECT_URI',
        'FRONTEND_URL',
        'ENVIRONMENT'
    ]
    
    all_set = True
    for var in required_vars:
        value = os.environ.get(var)
        if value:
            if var in ['GOOGLE_CLIENT_SECRET', 'SECRET_KEY']:
                print(f"✓ {var}: {'*' * 10} (hidden)")
            else:
                print(f"✓ {var}: {value}")
        else:
            print(f"✗ {var}: NOT SET")
            all_set = False
    
    print()
    return all_set

def test_backend_health():
    """Test if the backend is running."""
    print("=== Backend Health Check ===")
    try:
        response = requests.get('http://localhost:5000/')
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        print()
        return True
    except Exception as e:
        print(f"✗ Backend not accessible: {e}")
        print("Make sure the backend is running: cd gmail-unsubscriber-backend && python app.py")
        print()
        return False

def test_cors():
    """Test CORS configuration."""
    print("=== CORS Test ===")
    headers = {
        'Origin': 'http://localhost:8000'
    }
    
    try:
        response = requests.get('http://localhost:5000/api/auth/status', headers=headers)
        print(f"Status Code: {response.status_code}")
        
        # Check CORS headers
        cors_headers = {
            'Access-Control-Allow-Origin': response.headers.get('Access-Control-Allow-Origin'),
            'Access-Control-Allow-Credentials': response.headers.get('Access-Control-Allow-Credentials')
        }
        
        for header, value in cors_headers.items():
            if value:
                print(f"✓ {header}: {value}")
            else:
                print(f"✗ {header}: Not present")
        
        print()
        return True
    except Exception as e:
        print(f"✗ CORS test failed: {e}")
        print()
        return False

def test_auth_login():
    """Test the auth login endpoint."""
    print("=== Auth Login Test ===")
    
    # Create a session to maintain cookies
    session = requests.Session()
    
    try:
        response = session.get('http://localhost:5000/api/auth/login')
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            auth_url = data.get('auth_url')
            
            if auth_url:
                print("✓ Auth URL generated successfully")
                
                # Parse the auth URL
                parsed = urlparse(auth_url)
                params = parse_qs(parsed.query)
                
                print(f"  - Redirect URI: {params.get('redirect_uri', ['Not found'])[0]}")
                print(f"  - Client ID: {params.get('client_id', ['Not found'])[0][:20]}...")
                print(f"  - Scope: {params.get('scope', ['Not found'])[0]}")
                print(f"  - State: {params.get('state', ['Not found'])[0][:20]}...")
                
                # Check session cookies
                print("\nSession Cookies:")
                for cookie in session.cookies:
                    print(f"  - {cookie.name}: {cookie.value[:20]}...")
                
                return True, session
            else:
                print("✗ No auth URL in response")
                return False, None
        else:
            print(f"✗ Failed with status {response.status_code}")
            return False, None
            
    except Exception as e:
        print(f"✗ Auth login test failed: {e}")
        return False, None
    finally:
        print()

def test_session_persistence(session):
    """Test if session persists across requests."""
    print("=== Session Persistence Test ===")
    
    if not session:
        print("✗ No session to test")
        print()
        return False
    
    try:
        # Make another request with the same session
        response = session.get('http://localhost:5000/api/auth/status')
        print(f"Status Code: {response.status_code}")
        
        # Check if session cookies are maintained
        print("Session Cookies After Second Request:")
        for cookie in session.cookies:
            print(f"  - {cookie.name}: {cookie.value[:20]}...")
        
        print()
        return True
        
    except Exception as e:
        print(f"✗ Session persistence test failed: {e}")
        print()
        return False

def main():
    """Run all OAuth debug tests."""
    print("Gmail Unsubscriber OAuth Debug Script")
    print("=" * 40)
    print()
    
    # Check environment
    if not check_environment():
        print("✗ Environment check failed. Please set all required variables.")
        return
    
    # Test backend health
    if not test_backend_health():
        return
    
    # Test CORS
    test_cors()
    
    # Test auth login
    success, session = test_auth_login()
    
    # Test session persistence
    if success:
        test_session_persistence(session)
    
    print("=== Debug Summary ===")
    print("1. Check that all environment variables are set correctly")
    print("2. Ensure the backend is running on http://localhost:5000")
    print("3. Ensure the frontend is running on http://localhost:8000")
    print("4. Check that Google OAuth credentials are valid")
    print("5. Verify redirect URI matches Google Console configuration")
    print()
    print("To test the full OAuth flow:")
    print("1. Open http://localhost:8000 in your browser")
    print("2. Open browser DevTools (F12) and go to Network tab")
    print("3. Click 'Sign in with Google'")
    print("4. Watch the network requests and console logs")
    print("5. Check backend logs for detailed OAuth debug info")

if __name__ == '__main__':
    main()