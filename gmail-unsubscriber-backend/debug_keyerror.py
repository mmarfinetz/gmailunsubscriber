#!/usr/bin/env python3
"""
Debug script to understand the KeyError issue with user email address.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import user_stats, user_activities, add_activity
import json

def test_user_stats_access():
    """Test user stats dictionary access."""
    print("Testing user stats dictionary access...")
    
    # Test email address as user_id
    user_id = "mitchmarfinetz@gmail.com"
    
    print(f"Initial user_stats keys: {list(user_stats.keys())}")
    print(f"user_id: {user_id}")
    print(f"user_id in user_stats: {user_id in user_stats}")
    
    # Initialize user stats
    if user_id not in user_stats:
        user_stats[user_id] = {
            "total_scanned": 0,
            "total_unsubscribed": 0,
            "time_saved": 0
        }
        print(f"Initialized stats for user: {user_id}")
    
    print(f"After init user_stats keys: {list(user_stats.keys())}")
    print(f"user_id in user_stats: {user_id in user_stats}")
    
    # Test accessing the stats
    try:
        print(f"Accessing user_stats['{user_id}']...")
        stats = user_stats[user_id]
        print(f"Success! Stats: {stats}")
        
        # Test incrementing
        user_stats[user_id]["total_scanned"] += 1
        print(f"Incremented total_scanned: {user_stats[user_id]['total_scanned']}")
        
    except KeyError as e:
        print(f"KeyError when accessing user_stats: {e}")
        print(f"Available keys: {list(user_stats.keys())}")
        
    # Test add_activity
    try:
        print(f"Testing add_activity...")
        add_activity(user_id, "test", "Test activity")
        print(f"Success! Activities: {len(user_activities.get(user_id, []))}")
        
    except Exception as e:
        print(f"Error in add_activity: {e}")


def test_string_encoding():
    """Test if there are any string encoding issues."""
    print("\nTesting string encoding...")
    
    user_id = "mitchmarfinetz@gmail.com"
    
    # Test different representations
    print(f"Original: {repr(user_id)}")
    print(f"Encoded: {user_id.encode('utf-8')}")
    print(f"Length: {len(user_id)}")
    
    # Test if there are any hidden characters
    for i, char in enumerate(user_id):
        if ord(char) > 127:
            print(f"Non-ASCII character at position {i}: {repr(char)} (ord: {ord(char)})")


def test_dict_key_types():
    """Test dictionary key type consistency."""
    print("\nTesting dictionary key types...")
    
    test_dict = {}
    user_id = "mitchmarfinetz@gmail.com"
    
    # Test with string key
    test_dict[user_id] = "value"
    print(f"Set with string key: {user_id in test_dict}")
    
    # Test with different string representations
    user_id2 = str(user_id)
    print(f"Same as str(): {user_id2 in test_dict}")
    
    # Test key equality
    print(f"Keys equal: {user_id == user_id2}")
    print(f"Keys identical: {user_id is user_id2}")


def main():
    """Run all debug tests."""
    print("=" * 60)
    print("Debug: KeyError with user email address")
    print("=" * 60)
    
    try:
        test_user_stats_access()
        test_string_encoding()
        test_dict_key_types()
        
        print("\n" + "=" * 60)
        print("Debug tests completed successfully!")
        
    except Exception as e:
        print(f"\nDebug test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()