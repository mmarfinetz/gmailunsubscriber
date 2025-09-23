#!/usr/bin/env python3
"""Test script to verify the apply endpoint with create_auto_archive_filter works correctly."""

import requests
import json
import sys

def test_apply_with_filter():
    """Test the apply endpoint with create_auto_archive_filter enabled."""

    # Backend URL
    backend_url = "http://localhost:5000"

    # You need to get a valid token from authentication first
    # For testing, you can get this from the browser's localStorage after logging in
    token = input("Enter your JWT token (from browser localStorage): ").strip()

    if not token:
        print("❌ No token provided. Please authenticate first and get the token from browser.")
        return False

    # Test payload with create_auto_archive_filter = true
    test_data = {
        "items": [
            {
                "id": "test_message_id",
                "action": "label_archive"
            }
        ],
        "create_auto_archive_filter": True  # This should now work without causing 'bool' object is not callable
    }

    # Headers with authentication
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    print("Testing /api/unsubscribe/apply endpoint...")
    print(f"Payload: {json.dumps(test_data, indent=2)}")

    try:
        response = requests.post(
            f"{backend_url}/api/unsubscribe/apply",
            headers=headers,
            json=test_data
        )

        print(f"\nResponse status: {response.status_code}")
        print(f"Response body: {json.dumps(response.json(), indent=2)}")

        if response.status_code == 200:
            print("✅ Test PASSED: Apply endpoint works with create_auto_archive_filter=true")
            return True
        else:
            response_data = response.json()
            if "bool.*not callable" in str(response_data.get("error", "")):
                print("❌ Test FAILED: Still getting 'bool' object is not callable error")
            else:
                print(f"❌ Test FAILED with different error: {response_data}")
            return False

    except Exception as e:
        print(f"❌ Test FAILED with exception: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Apply Endpoint Fix for Name Collision")
    print("=" * 60)
    print("\nMake sure the backend is running at http://localhost:5000")
    print("You'll need a valid JWT token from a logged-in session.\n")

    success = test_apply_with_filter()

    if success:
        print("\n🎉 Fix verified successfully!")
    else:
        print("\n⚠️  Fix verification failed. Check the implementation.")

    sys.exit(0 if success else 1)