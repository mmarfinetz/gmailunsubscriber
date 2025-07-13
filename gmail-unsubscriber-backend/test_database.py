#!/usr/bin/env python3
"""
Test script for Gmail Unsubscriber database functionality.
Verifies that database operations work correctly.
"""

import os
import tempfile
import logging
from datetime import datetime
from database import initialize_database, get_db_manager

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_database_initialization():
    """Test database initialization."""
    print("Testing database initialization...")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        test_db_path = tmp_file.name
    
    try:
        success = initialize_database(test_db_path)
        assert success, "Database initialization failed"
        
        # Check if database file was created
        assert os.path.exists(test_db_path), "Database file was not created"
        
        # Check if we can get the manager
        db_manager = get_db_manager()
        assert db_manager is not None, "Database manager is None"
        
        print("✓ Database initialization test passed")
        return True
        
    finally:
        # Clean up
        if os.path.exists(test_db_path):
            os.unlink(test_db_path)

def test_user_stats_operations():
    """Test user statistics operations."""
    print("Testing user statistics operations...")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        test_db_path = tmp_file.name
    
    try:
        # Initialize database
        success = initialize_database(test_db_path)
        assert success, "Database initialization failed"
        
        db_manager = get_db_manager()
        
        # Create test data
        test_user_stats = {
            'test@example.com': {
                'total_scanned': 10,
                'total_unsubscribed': 5,
                'time_saved': 600,
                'domains_unsubscribed': {
                    'example.com': {
                        'count': 3,
                        'sender_name': 'Example Corp',
                        'emails': {'sender1@example.com', 'sender2@example.com'}
                    },
                    'test.org': {
                        'count': 2,
                        'sender_name': 'Test Organization',
                        'emails': {'info@test.org'}
                    }
                }
            },
            'user2@test.com': {
                'total_scanned': 20,
                'total_unsubscribed': 15,
                'time_saved': 1800,
                'domains_unsubscribed': {}
            }
        }
        
        # Save stats
        success = db_manager.save_user_stats(test_user_stats)
        assert success, "Failed to save user stats"
        
        # Load stats
        loaded_stats = db_manager.load_user_stats()
        assert len(loaded_stats) == 2, f"Expected 2 users, got {len(loaded_stats)}"
        
        # Verify data integrity
        for user_id, original_stats in test_user_stats.items():
            assert user_id in loaded_stats, f"User {user_id} not found in loaded stats"
            loaded_user_stats = loaded_stats[user_id]
            
            # Check basic stats
            assert loaded_user_stats['total_scanned'] == original_stats['total_scanned']
            assert loaded_user_stats['total_unsubscribed'] == original_stats['total_unsubscribed']
            assert loaded_user_stats['time_saved'] == original_stats['time_saved']
            
            # Check domains
            original_domains = original_stats.get('domains_unsubscribed', {})
            loaded_domains = loaded_user_stats.get('domains_unsubscribed', {})
            assert len(loaded_domains) == len(original_domains)
            
            for domain, original_domain_info in original_domains.items():
                assert domain in loaded_domains
                loaded_domain_info = loaded_domains[domain]
                assert loaded_domain_info['count'] == original_domain_info['count']
                assert loaded_domain_info['sender_name'] == original_domain_info['sender_name']
                assert loaded_domain_info['emails'] == original_domain_info['emails']
        
        print("✓ User statistics operations test passed")
        return True
        
    finally:
        # Clean up
        if os.path.exists(test_db_path):
            os.unlink(test_db_path)

def test_user_activities_operations():
    """Test user activities operations."""
    print("Testing user activities operations...")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        test_db_path = tmp_file.name
    
    try:
        # Initialize database
        success = initialize_database(test_db_path)
        assert success, "Database initialization failed"
        
        db_manager = get_db_manager()
        
        # Create test data
        test_user_activities = {
            'test@example.com': [
                {
                    'type': 'info',
                    'message': 'Successfully connected Gmail account',
                    'time': datetime.now().isoformat()
                },
                {
                    'type': 'success',
                    'message': 'Unsubscribed from example.com',
                    'time': datetime.now().isoformat(),
                    'metadata': {'domain': 'example.com', 'count': 3}
                },
                {
                    'type': 'warning',
                    'message': 'No unsubscribe link found',
                    'time': datetime.now().isoformat()
                }
            ],
            'user2@test.com': [
                {
                    'type': 'info',
                    'message': 'Started email scan',
                    'time': datetime.now().isoformat()
                }
            ]
        }
        
        # Save activities
        success = db_manager.save_user_activities(test_user_activities)
        assert success, "Failed to save user activities"
        
        # Load activities
        loaded_activities = db_manager.load_user_activities()
        assert len(loaded_activities) == 2, f"Expected 2 users, got {len(loaded_activities)}"
        
        # Verify data integrity
        for user_id, original_activities in test_user_activities.items():
            assert user_id in loaded_activities, f"User {user_id} not found in loaded activities"
            loaded_user_activities = loaded_activities[user_id]
            
            assert len(loaded_user_activities) == len(original_activities)
            
            for i, original_activity in enumerate(original_activities):
                loaded_activity = loaded_user_activities[i]
                assert loaded_activity['type'] == original_activity['type']
                assert loaded_activity['message'] == original_activity['message']
                
                # Check metadata if present
                if 'metadata' in original_activity:
                    assert 'metadata' in loaded_activity
                    assert loaded_activity['metadata'] == original_activity['metadata']
        
        print("✓ User activities operations test passed")
        return True
        
    finally:
        # Clean up
        if os.path.exists(test_db_path):
            os.unlink(test_db_path)

def test_single_user_operations():
    """Test single user operations."""
    print("Testing single user operations...")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        test_db_path = tmp_file.name
    
    try:
        # Initialize database
        success = initialize_database(test_db_path)
        assert success, "Database initialization failed"
        
        db_manager = get_db_manager()
        
        user_id = 'single_test@example.com'
        
        # Test single user stats save
        test_stats = {
            'total_scanned': 100,
            'total_unsubscribed': 50,
            'time_saved': 3000,
            'domains_unsubscribed': {
                'newsletter.com': {
                    'count': 10,
                    'sender_name': 'Newsletter Service',
                    'emails': {'news@newsletter.com'}
                }
            }
        }
        
        success = db_manager.save_single_user_stats(user_id, test_stats)
        assert success, "Failed to save single user stats"
        
        # Test single user activity save
        test_activity = {
            'type': 'success',
            'message': 'Test activity message',
            'time': datetime.now().isoformat(),
            'metadata': {'test': 'data'}
        }
        
        success = db_manager.save_single_user_activity(user_id, test_activity)
        assert success, "Failed to save single user activity"
        
        # Verify by loading all data
        all_stats = db_manager.load_user_stats()
        all_activities = db_manager.load_user_activities()
        
        assert user_id in all_stats
        assert user_id in all_activities
        assert len(all_activities[user_id]) == 1
        assert all_activities[user_id][0]['message'] == test_activity['message']
        
        print("✓ Single user operations test passed")
        return True
        
    finally:
        # Clean up
        if os.path.exists(test_db_path):
            os.unlink(test_db_path)

def test_database_stats():
    """Test database statistics."""
    print("Testing database statistics...")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        test_db_path = tmp_file.name
    
    try:
        # Initialize database
        success = initialize_database(test_db_path)
        assert success, "Database initialization failed"
        
        db_manager = get_db_manager()
        
        # Add some test data
        test_user_stats = {
            'user1@test.com': {
                'total_scanned': 10,
                'total_unsubscribed': 5,
                'time_saved': 300,
                'domains_unsubscribed': {
                    'example.com': {
                        'count': 2,
                        'sender_name': 'Example',
                        'emails': {'test@example.com'}
                    }
                }
            }
        }
        
        test_user_activities = {
            'user1@test.com': [
                {
                    'type': 'info',
                    'message': 'Test message',
                    'time': datetime.now().isoformat()
                }
            ]
        }
        
        db_manager.save_user_stats(test_user_stats)
        db_manager.save_user_activities(test_user_activities)
        
        # Get database stats
        stats = db_manager.get_database_stats()
        
        assert 'total_users' in stats
        assert 'total_activities' in stats
        assert 'total_domains' in stats
        assert 'db_size_bytes' in stats
        
        assert stats['total_users'] >= 1
        assert stats['total_activities'] >= 1
        assert stats['total_domains'] >= 1
        assert stats['db_size_bytes'] > 0
        
        print("✓ Database statistics test passed")
        return True
        
    finally:
        # Clean up
        if os.path.exists(test_db_path):
            os.unlink(test_db_path)

def run_all_tests():
    """Run all database tests."""
    print("Gmail Unsubscriber Database Tests")
    print("=" * 50)
    
    tests = [
        test_database_initialization,
        test_user_stats_operations,
        test_user_activities_operations,
        test_single_user_operations,
        test_database_stats
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                print(f"✗ {test_func.__name__} failed")
        except Exception as e:
            failed += 1
            print(f"✗ {test_func.__name__} failed with exception: {e}")
    
    print("\n" + "=" * 50)
    print(f"Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed!")
        return True
    else:
        print("❌ Some tests failed!")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)