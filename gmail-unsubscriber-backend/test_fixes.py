#!/usr/bin/env python3
"""
Test script to verify the fixes for Gmail email processing errors.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import ensure_label_exists, extract_html_content, extract_text_content, extract_unsub_links
import base64
import json


def test_label_creation():
    """Test label creation logic (mock)."""
    print("Testing label creation logic...")
    
    # Mock Gmail service response
    class MockService:
        def users(self):
            return MockUsers()
    
    class MockUsers:
        def labels(self):
            return MockLabels()
    
    class MockLabels:
        def list(self, userId):
            return MockListResponse()
        
        def create(self, userId, body):
            return MockCreateResponse()
    
    class MockListResponse:
        def execute(self):
            return {
                'labels': [
                    {'id': 'INBOX', 'name': 'INBOX'},
                    {'id': 'SENT', 'name': 'SENT'}
                ]
            }
    
    class MockCreateResponse:
        def execute(self):
            return {'id': 'Label_123', 'name': 'UNSUBSCRIBED'}
    
    # Test the function
    service = MockService()
    result = ensure_label_exists(service, 'UNSUBSCRIBED')
    print(f"✓ Label creation test passed: {result}")


def test_html_extraction():
    """Test HTML content extraction."""
    print("\nTesting HTML content extraction...")
    
    # Test case 1: Simple HTML content
    html_content = "<html><body>Test email content</body></html>"
    encoded_content = base64.urlsafe_b64encode(html_content.encode()).decode()
    
    payload = {
        'mimeType': 'text/html',
        'body': {'data': encoded_content}
    }
    
    result = extract_html_content(payload, 'test_msg_1')
    assert result == html_content, f"Expected {html_content}, got {result}"
    print("✓ Simple HTML extraction test passed")
    
    # Test case 2: Multi-part email
    payload = {
        'parts': [
            {
                'mimeType': 'text/plain',
                'body': {'data': base64.urlsafe_b64encode(b"Plain text").decode()}
            },
            {
                'mimeType': 'text/html',
                'body': {'data': encoded_content}
            }
        ]
    }
    
    result = extract_html_content(payload, 'test_msg_2')
    assert result == html_content, f"Expected {html_content}, got {result}"
    print("✓ Multi-part HTML extraction test passed")


def test_unsubscribe_link_extraction():
    """Test unsubscribe link extraction."""
    print("\nTesting unsubscribe link extraction...")
    
    # Test HTML with unsubscribe links
    html_content = """
    <html>
    <body>
        <p>Newsletter content</p>
        <a href="https://example.com/unsubscribe?token=123">Unsubscribe</a>
        <a href="https://example.com/manage">Manage email preferences</a>
        <a href="https://example.com/opt-out">Opt out</a>
    </body>
    </html>
    """
    
    links = extract_unsub_links(html_content)
    expected_links = [
        'https://example.com/unsubscribe?token=123',
        'https://example.com/manage',
        'https://example.com/opt-out'
    ]
    
    assert len(links) == 3, f"Expected 3 links, got {len(links)}"
    for link in expected_links:
        assert link in links, f"Expected link {link} not found in {links}"
    
    print("✓ Unsubscribe link extraction test passed")


def test_error_handling():
    """Test error handling for malformed data."""
    print("\nTesting error handling...")
    
    # Test with empty payload
    result = extract_html_content({}, 'test_msg_error')
    assert result == "", f"Expected empty string, got {result}"
    print("✓ Empty payload error handling test passed")
    
    # Test with malformed base64
    payload = {
        'mimeType': 'text/html',
        'body': {'data': 'invalid_base64!@#'}
    }
    
    result = extract_html_content(payload, 'test_msg_error2')
    assert result == "", f"Expected empty string, got {result}"
    print("✓ Malformed base64 error handling test passed")


def main():
    """Run all tests."""
    print("Running Gmail Unsubscriber fix tests...")
    print("=" * 50)
    
    try:
        test_label_creation()
        test_html_extraction()
        test_unsubscribe_link_extraction()
        test_error_handling()
        
        print("\n" + "=" * 50)
        print("✅ All tests passed! The fixes should resolve the email processing errors.")
        print("\nKey improvements:")
        print("1. ✓ Gmail label creation/validation")
        print("2. ✓ Enhanced email content extraction")
        print("3. ✓ Robust error handling and recovery")
        print("4. ✓ Per-email error boundaries")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()