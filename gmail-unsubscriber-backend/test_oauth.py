#!/usr/bin/env python3
"""Test OAuth configuration and state management."""

import os
import json
from app import app

def test_oauth_config():
    """Test OAuth configuration settings."""
    print("Testing OAuth configuration...")
    print(f"Environment: {os.environ.get('ENVIRONMENT', 'NOT SET')}")
    print(f"Frontend URL: {os.environ.get('FRONTEND_URL', 'NOT SET')}")
    print(f"Session Cookie Secure: {app.config.get('SESSION_COOKIE_SECURE')}")
    print(f"Session Cookie SameSite: {app.config.get('SESSION_COOKIE_SAMESITE')}")
    print(f"Session Cookie HTTPOnly: {app.config.get('SESSION_COOKIE_HTTPONLY')}")
    print(f"Session Cookie Name: {app.config.get('SESSION_COOKIE_NAME')}")
    print()

def test_oauth_endpoints():
    """Test OAuth endpoints."""
    with app.test_client() as client:
        # Test session debug endpoint
        print("Testing session debug endpoint...")
        response = client.get('/api/session/debug')
        print(f"Session debug status: {response.status_code}")
        
        if response.status_code == 200:
            data = json.loads(response.data)
            print("Session cookie config:")
            for k, v in data['session_cookie_config'].items():
                print(f"  {k}: {v}")
            print("Environment info:")
            for k, v in data['environment_info'].items():
                print(f"  {k}: {v}")
        print()
        
        # Test OAuth login endpoint
        print("Testing OAuth login endpoint...")
        response = client.get('/api/auth/login')
        print(f"OAuth login status: {response.status_code}")
        
        if response.status_code == 200:
            data = json.loads(response.data)
            print("OAuth login response structure:")
            print(f"  Has auth_url: {'auth_url' in data}")
            if 'auth_url' in data:
                print(f"  Auth URL starts with: {data['auth_url'][:50]}...")
            
            # Check if state was stored
            debug_response = client.get('/api/session/debug')
            if debug_response.status_code == 200:
                debug_data = json.loads(debug_response.data)
                state_info = debug_data['stored_state']
                print("State storage after login:")
                for k, v in state_info.items():
                    if k == 'oauth2_state' and v != 'Not found':
                        print(f"  {k}: {v[:20]}... (truncated)")
                    else:
                        print(f"  {k}: {v}")

if __name__ == '__main__':
    test_oauth_config()
    test_oauth_endpoints()
    print("OAuth testing completed successfully!")