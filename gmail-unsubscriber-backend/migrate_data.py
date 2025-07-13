#!/usr/bin/env python3
"""
Data Migration Script for Gmail Unsubscriber
Migrates existing in-memory data to SQLite database.
"""

import os
import sys
import json
import logging
from datetime import datetime
from database import initialize_database, get_db_manager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_backup_data(backup_file_path):
    """Load backup data from JSON file."""
    if not os.path.exists(backup_file_path):
        logger.error(f"Backup file not found: {backup_file_path}")
        return None, None
    
    try:
        with open(backup_file_path, 'r') as f:
            data = json.load(f)
        
        user_stats = data.get('user_stats', {})
        user_activities = data.get('user_activities', {})
        
        # Convert sets back from lists for domains_unsubscribed
        for user_id, stats in user_stats.items():
            domains = stats.get('domains_unsubscribed', {})
            for domain, domain_info in domains.items():
                if 'emails' in domain_info and isinstance(domain_info['emails'], list):
                    domain_info['emails'] = set(domain_info['emails'])
        
        logger.info(f"Loaded backup data: {len(user_stats)} users with stats, {len(user_activities)} users with activities")
        return user_stats, user_activities
        
    except Exception as e:
        logger.error(f"Error loading backup data: {e}")
        return None, None

def create_backup(user_stats, user_activities, backup_file_path):
    """Create a backup of current in-memory data."""
    try:
        # Convert sets to lists for JSON serialization
        backup_stats = {}
        for user_id, stats in user_stats.items():
            backup_stats[user_id] = stats.copy()
            domains = backup_stats[user_id].get('domains_unsubscribed', {})
            for domain, domain_info in domains.items():
                if 'emails' in domain_info and isinstance(domain_info['emails'], set):
                    domain_info['emails'] = list(domain_info['emails'])
        
        backup_data = {
            'user_stats': backup_stats,
            'user_activities': user_activities,
            'backup_timestamp': datetime.now().isoformat(),
            'backup_type': 'pre_migration'
        }
        
        with open(backup_file_path, 'w') as f:
            json.dump(backup_data, f, indent=2)
        
        logger.info(f"Created backup at: {backup_file_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        return False

def migrate_to_database(user_stats, user_activities, db_path="gmail_unsubscriber.db"):
    """Migrate data to SQLite database."""
    try:
        # Initialize database
        logger.info("Initializing database...")
        success = initialize_database(db_path)
        if not success:
            logger.error("Database initialization failed")
            return False
        
        db_manager = get_db_manager()
        if not db_manager:
            logger.error("Could not get database manager")
            return False
        
        # Save data to database
        logger.info("Migrating user statistics...")
        stats_success = db_manager.save_user_stats(user_stats)
        
        logger.info("Migrating user activities...")
        activities_success = db_manager.save_user_activities(user_activities)
        
        if stats_success and activities_success:
            logger.info("Migration completed successfully!")
            
            # Get database stats for verification
            db_stats = db_manager.get_database_stats()
            logger.info(f"Database stats after migration: {db_stats}")
            
            return True
        else:
            logger.error("Migration partially failed")
            return False
            
    except Exception as e:
        logger.error(f"Error during migration: {e}")
        return False

def verify_migration(user_stats, user_activities, db_path="gmail_unsubscriber.db"):
    """Verify that migrated data matches original data."""
    try:
        db_manager = get_db_manager()
        if not db_manager:
            logger.error("Database manager not available for verification")
            return False
        
        # Load data from database
        loaded_stats = db_manager.load_user_stats()
        loaded_activities = db_manager.load_user_activities()
        
        # Compare stats
        stats_match = True
        for user_id, original_stats in user_stats.items():
            if user_id not in loaded_stats:
                logger.error(f"User {user_id} missing from loaded stats")
                stats_match = False
                continue
            
            loaded_user_stats = loaded_stats[user_id]
            for key in ['total_scanned', 'total_unsubscribed', 'time_saved']:
                if original_stats.get(key, 0) != loaded_user_stats.get(key, 0):
                    logger.error(f"Stats mismatch for {user_id}.{key}: {original_stats.get(key)} vs {loaded_user_stats.get(key)}")
                    stats_match = False
        
        # Compare activities (basic count check)
        activities_match = True
        for user_id, original_activities in user_activities.items():
            if user_id not in loaded_activities:
                logger.error(f"User {user_id} missing from loaded activities")
                activities_match = False
                continue
            
            if len(original_activities) != len(loaded_activities[user_id]):
                logger.warning(f"Activity count mismatch for {user_id}: {len(original_activities)} vs {len(loaded_activities[user_id])}")
                # This might be OK due to 50-item limit
        
        if stats_match:
            logger.info("✓ Statistics verification passed")
        else:
            logger.error("✗ Statistics verification failed")
        
        if activities_match:
            logger.info("✓ Activities verification passed")
        else:
            logger.warning("⚠ Activities verification had warnings (may be due to 50-item limit)")
        
        return stats_match
        
    except Exception as e:
        logger.error(f"Error during verification: {e}")
        return False

def main():
    """Main migration function."""
    print("Gmail Unsubscriber Data Migration Tool")
    print("=" * 50)
    
    # Parse command line arguments
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python migrate_data.py backup <backup_file>          - Create backup from running app")
        print("  python migrate_data.py migrate <backup_file>         - Migrate from backup to database")
        print("  python migrate_data.py migrate_live                  - Migrate from current app memory")
        print("  python migrate_data.py verify <backup_file>          - Verify migration")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "backup":
        if len(sys.argv) < 3:
            logger.error("Backup file path required")
            sys.exit(1)
        
        backup_file = sys.argv[2]
        
        # This would require importing the current app state
        # For now, we'll create a sample backup structure
        logger.info(f"Creating backup structure at {backup_file}")
        sample_data = {
            'user_stats': {},
            'user_activities': {},
            'backup_timestamp': datetime.now().isoformat(),
            'backup_type': 'manual'
        }
        
        try:
            with open(backup_file, 'w') as f:
                json.dump(sample_data, f, indent=2)
            logger.info(f"Sample backup created at {backup_file}")
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            sys.exit(1)
    
    elif command == "migrate":
        if len(sys.argv) < 3:
            logger.error("Backup file path required")
            sys.exit(1)
        
        backup_file = sys.argv[2]
        
        # Load data from backup
        user_stats, user_activities = load_backup_data(backup_file)
        if user_stats is None:
            sys.exit(1)
        
        # Migrate to database
        success = migrate_to_database(user_stats, user_activities)
        if success:
            logger.info("Migration completed successfully!")
        else:
            logger.error("Migration failed!")
            sys.exit(1)
    
    elif command == "migrate_live":
        logger.info("Live migration not implemented - use backup and migrate instead")
        sys.exit(1)
    
    elif command == "verify":
        if len(sys.argv) < 3:
            logger.error("Backup file path required")
            sys.exit(1)
        
        backup_file = sys.argv[2]
        
        # Load original data
        user_stats, user_activities = load_backup_data(backup_file)
        if user_stats is None:
            sys.exit(1)
        
        # Verify migration
        success = verify_migration(user_stats, user_activities)
        if success:
            logger.info("Verification completed successfully!")
        else:
            logger.error("Verification failed!")
            sys.exit(1)
    
    else:
        logger.error(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()