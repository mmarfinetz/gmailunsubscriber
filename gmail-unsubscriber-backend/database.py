"""
Database module for Gmail Unsubscriber persistence.
Provides SQLite-based persistent storage for user statistics and activities.
"""

import sqlite3
import json
import logging
import threading
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages SQLite database operations for Gmail Unsubscriber."""
    
    def __init__(self, db_path: str = "gmail_unsubscriber.db"):
        """Initialize database manager with specified database path."""
        self.db_path = db_path
        self.lock = threading.Lock()
        self._ensure_db_directory()
        logger.info(f"Database manager initialized with path: {self.db_path}")
    
    def _ensure_db_directory(self):
        """Ensure the directory for the database file exists."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"Created database directory: {db_dir}")
    
    @contextmanager
    def get_connection(self):
        """Get a database connection with proper resource management."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row  # Enable row access by column name
            # Enable WAL mode for better concurrency
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.execute('PRAGMA cache_size=10000')
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def initialize_database(self) -> bool:
        """Initialize database with required tables. Returns True if successful."""
        try:
            with self.lock:
                with self.get_connection() as conn:
                    # Create users table
                    conn.execute('''
                        CREATE TABLE IF NOT EXISTS users (
                            user_id TEXT PRIMARY KEY,
                            email TEXT UNIQUE NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')
                    
                    # Create user_stats table
                    conn.execute('''
                        CREATE TABLE IF NOT EXISTS user_stats (
                            user_id TEXT PRIMARY KEY,
                            total_scanned INTEGER DEFAULT 0,
                            total_unsubscribed INTEGER DEFAULT 0,
                            time_saved INTEGER DEFAULT 0,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES users (user_id)
                        )
                    ''')
                    
                    # Create user_activities table
                    conn.execute('''
                        CREATE TABLE IF NOT EXISTS user_activities (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id TEXT NOT NULL,
                            type TEXT NOT NULL,
                            message TEXT NOT NULL,
                            metadata TEXT,
                            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES users (user_id)
                        )
                    ''')
                    
                    # Create domains_unsubscribed table
                    conn.execute('''
                        CREATE TABLE IF NOT EXISTS domains_unsubscribed (
                            user_id TEXT NOT NULL,
                            domain TEXT NOT NULL,
                            sender_name TEXT,
                            count INTEGER DEFAULT 0,
                            emails_json TEXT DEFAULT '[]',
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            PRIMARY KEY (user_id, domain),
                            FOREIGN KEY (user_id) REFERENCES users (user_id)
                        )
                    ''')
                    
                    # Create operations_history table for undo functionality
                    conn.execute('''
                        CREATE TABLE IF NOT EXISTS operations_history (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id TEXT NOT NULL,
                            operation_id TEXT UNIQUE NOT NULL,
                            payload_json TEXT NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            undone INTEGER DEFAULT 0,
                            FOREIGN KEY (user_id) REFERENCES users (user_id)
                        )
                    ''')

                    # Create stats_history table for tracking changes over time
                    conn.execute('''
                        CREATE TABLE IF NOT EXISTS stats_history (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id TEXT NOT NULL,
                            total_scanned INTEGER DEFAULT 0,
                            total_unsubscribed INTEGER DEFAULT 0,
                            time_saved INTEGER DEFAULT 0,
                            emails_deleted INTEGER DEFAULT 0,
                            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES users (user_id)
                        )
                    ''')

                    # Create indexes for better performance
                    conn.execute('CREATE INDEX IF NOT EXISTS idx_activities_user_id ON user_activities (user_id)')
                    conn.execute('CREATE INDEX IF NOT EXISTS idx_activities_timestamp ON user_activities (timestamp)')
                    conn.execute('CREATE INDEX IF NOT EXISTS idx_domains_user_id ON domains_unsubscribed (user_id)')
                    conn.execute('CREATE INDEX IF NOT EXISTS idx_operations_user_id ON operations_history (user_id)')
                    conn.execute('CREATE INDEX IF NOT EXISTS idx_operations_operation_id ON operations_history (operation_id)')
                    conn.execute('CREATE INDEX IF NOT EXISTS idx_stats_history_user_id ON stats_history (user_id)')
                    conn.execute('CREATE INDEX IF NOT EXISTS idx_stats_history_recorded_at ON stats_history (recorded_at)')

                    conn.commit()
                    logger.info("Database tables and indexes created successfully")
                    return True
                    
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            return False
    
    def ensure_user_exists(self, user_id: str) -> bool:
        """Ensure a user exists in the database. Creates if missing."""
        try:
            with self.get_connection() as conn:
                # Check if user exists
                cursor = conn.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
                if cursor.fetchone():
                    # Update last_active
                    conn.execute(
                        'UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?',
                        (user_id,)
                    )
                else:
                    # Create new user
                    conn.execute(
                        'INSERT INTO users (user_id, email) VALUES (?, ?)',
                        (user_id, user_id)  # Using user_id as email for simplicity
                    )
                    # Create initial stats record
                    conn.execute(
                        'INSERT INTO user_stats (user_id) VALUES (?)',
                        (user_id,)
                    )
                    logger.info(f"Created new user: {user_id}")
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to ensure user exists {user_id}: {e}")
            return False
    
    def load_user_stats(self) -> Dict[str, Dict[str, Any]]:
        """Load all user statistics from database into memory format."""
        try:
            user_stats = {}
            
            with self.get_connection() as conn:
                # Load basic stats
                cursor = conn.execute('''
                    SELECT user_id, total_scanned, total_unsubscribed, time_saved
                    FROM user_stats
                ''')
                
                for row in cursor:
                    user_stats[row['user_id']] = {
                        'total_scanned': row['total_scanned'],
                        'total_unsubscribed': row['total_unsubscribed'],
                        'time_saved': row['time_saved'],
                        'domains_unsubscribed': {}
                    }
                
                # Load domain statistics
                cursor = conn.execute('''
                    SELECT user_id, domain, sender_name, count, emails_json
                    FROM domains_unsubscribed
                ''')
                
                for row in cursor:
                    user_id = row['user_id']
                    if user_id in user_stats:
                        try:
                            emails_list = json.loads(row['emails_json'] or '[]')
                            emails_set = set(emails_list)
                        except json.JSONDecodeError:
                            emails_set = set()
                        
                        user_stats[user_id]['domains_unsubscribed'][row['domain']] = {
                            'count': row['count'],
                            'sender_name': row['sender_name'] or row['domain'],
                            'emails': emails_set
                        }
            
            logger.info(f"Loaded stats for {len(user_stats)} users from database")
            return user_stats
            
        except Exception as e:
            logger.error(f"Failed to load user stats: {e}")
            return {}
    
    def load_user_activities(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load all user activities from database into memory format."""
        try:
            user_activities = {}
            
            with self.get_connection() as conn:
                # Load activities ordered by timestamp (newest first)
                cursor = conn.execute('''
                    SELECT user_id, type, message, metadata, timestamp
                    FROM user_activities
                    ORDER BY user_id, timestamp DESC
                ''')
                
                for row in cursor:
                    user_id = row['user_id']
                    if user_id not in user_activities:
                        user_activities[user_id] = []
                    
                    activity = {
                        'type': row['type'],
                        'message': row['message'],
                        'time': row['timestamp']
                    }
                    
                    # Add metadata if present
                    if row['metadata']:
                        try:
                            activity['metadata'] = json.loads(row['metadata'])
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid metadata JSON for activity: {row['metadata']}")
                    
                    user_activities[user_id].append(activity)
                
                # Limit to 50 most recent activities per user (matching in-memory limit)
                for user_id in user_activities:
                    user_activities[user_id] = user_activities[user_id][:50]
            
            logger.info(f"Loaded activities for {len(user_activities)} users from database")
            return user_activities
            
        except Exception as e:
            logger.error(f"Failed to load user activities: {e}")
            return {}
    
    def save_user_stats(self, user_stats: Dict[str, Dict[str, Any]]) -> bool:
        """Save all user statistics from memory to database."""
        try:
            with self.lock:
                with self.get_connection() as conn:
                    for user_id, stats in user_stats.items():
                        # Ensure user exists
                        self.ensure_user_exists(user_id)
                        
                        # Update basic stats
                        conn.execute('''
                            UPDATE user_stats 
                            SET total_scanned = ?, total_unsubscribed = ?, time_saved = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE user_id = ?
                        ''', (
                            stats.get('total_scanned', 0),
                            stats.get('total_unsubscribed', 0),
                            stats.get('time_saved', 0),
                            user_id
                        ))
                        
                        # Update domain statistics
                        domains_data = stats.get('domains_unsubscribed', {})
                        for domain, domain_info in domains_data.items():
                            emails_set = domain_info.get('emails', set())
                            emails_json = json.dumps(list(emails_set))
                            
                            conn.execute('''
                                INSERT OR REPLACE INTO domains_unsubscribed 
                                (user_id, domain, sender_name, count, emails_json, updated_at)
                                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                            ''', (
                                user_id,
                                domain,
                                domain_info.get('sender_name', domain),
                                domain_info.get('count', 0),
                                emails_json
                            ))
                    
                    conn.commit()
                    logger.info(f"Saved stats for {len(user_stats)} users to database")
                    return True
                    
        except Exception as e:
            logger.error(f"Failed to save user stats: {e}")
            return False
    
    def save_user_activities(self, user_activities: Dict[str, List[Dict[str, Any]]]) -> bool:
        """Save all user activities from memory to database."""
        try:
            with self.lock:
                with self.get_connection() as conn:
                    for user_id, activities in user_activities.items():
                        # Ensure user exists
                        self.ensure_user_exists(user_id)
                        
                        # Clear existing activities for this user (we'll re-insert all)
                        conn.execute('DELETE FROM user_activities WHERE user_id = ?', (user_id,))
                        
                        # Insert activities (newest first, but we'll reverse to maintain order)
                        for activity in reversed(activities):
                            metadata_json = None
                            if activity.get('metadata'):
                                metadata_json = json.dumps(activity['metadata'])
                            
                            conn.execute('''
                                INSERT INTO user_activities (user_id, type, message, metadata, timestamp)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (
                                user_id,
                                activity.get('type', 'info'),
                                activity.get('message', ''),
                                metadata_json,
                                activity.get('time', datetime.now().isoformat())
                            ))
                    
                    conn.commit()
                    logger.info(f"Saved activities for {len(user_activities)} users to database")
                    return True
                    
        except Exception as e:
            logger.error(f"Failed to save user activities: {e}")
            return False
    
    def save_single_user_stats(self, user_id: str, stats: Dict[str, Any]) -> bool:
        """Save statistics for a single user. More efficient for individual updates."""
        try:
            with self.get_connection() as conn:
                # Ensure user exists
                self.ensure_user_exists(user_id)
                
                # Update basic stats
                conn.execute('''
                    UPDATE user_stats 
                    SET total_scanned = ?, total_unsubscribed = ?, time_saved = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                ''', (
                    stats.get('total_scanned', 0),
                    stats.get('total_unsubscribed', 0),
                    stats.get('time_saved', 0),
                    user_id
                ))
                
                # Update domain statistics
                domains_data = stats.get('domains_unsubscribed', {})
                for domain, domain_info in domains_data.items():
                    emails_set = domain_info.get('emails', set())
                    emails_json = json.dumps(list(emails_set))
                    
                    conn.execute('''
                        INSERT OR REPLACE INTO domains_unsubscribed 
                        (user_id, domain, sender_name, count, emails_json, updated_at)
                        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (
                        user_id,
                        domain,
                        domain_info.get('sender_name', domain),
                        domain_info.get('count', 0),
                        emails_json
                    ))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to save stats for user {user_id}: {e}")
            return False
    
    def save_single_user_activity(self, user_id: str, activity: Dict[str, Any]) -> bool:
        """Save a single activity for a user. More efficient for individual updates."""
        try:
            with self.get_connection() as conn:
                # Ensure user exists
                self.ensure_user_exists(user_id)
                
                metadata_json = None
                if activity.get('metadata'):
                    metadata_json = json.dumps(activity['metadata'])
                
                conn.execute('''
                    INSERT INTO user_activities (user_id, type, message, metadata, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    user_id,
                    activity.get('type', 'info'),
                    activity.get('message', ''),
                    metadata_json,
                    activity.get('time', datetime.now().isoformat())
                ))
                
                # Clean up old activities (keep only 50 most recent)
                conn.execute('''
                    DELETE FROM user_activities 
                    WHERE user_id = ? AND id NOT IN (
                        SELECT id FROM user_activities 
                        WHERE user_id = ? 
                        ORDER BY timestamp DESC 
                        LIMIT 50
                    )
                ''', (user_id, user_id))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to save activity for user {user_id}: {e}")
            return False
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics for monitoring."""
        try:
            with self.get_connection() as conn:
                stats = {}
                
                # Count users
                cursor = conn.execute('SELECT COUNT(*) FROM users')
                stats['total_users'] = cursor.fetchone()[0]
                
                # Count activities
                cursor = conn.execute('SELECT COUNT(*) FROM user_activities')
                stats['total_activities'] = cursor.fetchone()[0]
                
                # Count domains
                cursor = conn.execute('SELECT COUNT(*) FROM domains_unsubscribed')
                stats['total_domains'] = cursor.fetchone()[0]
                
                # Database file size
                if os.path.exists(self.db_path):
                    stats['db_size_bytes'] = os.path.getsize(self.db_path)
                else:
                    stats['db_size_bytes'] = 0
                
                # Most recent activity
                cursor = conn.execute('SELECT MAX(timestamp) FROM user_activities')
                stats['last_activity'] = cursor.fetchone()[0]
                
                return stats

        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {}

    def save_stats_snapshot(self, user_id: str, stats: Dict[str, Any]) -> bool:
        """Save a snapshot of user statistics to history."""
        try:
            with self.get_connection() as conn:
                conn.execute('''
                    INSERT INTO stats_history
                    (user_id, total_scanned, total_unsubscribed, time_saved, emails_deleted)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    user_id,
                    stats.get('total_scanned', 0),
                    stats.get('total_unsubscribed', 0),
                    stats.get('time_saved', 0),
                    stats.get('total_unsubscribed', 0)  # emails_deleted is same as total_unsubscribed
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to save stats snapshot for user {user_id}: {e}")
            return False

    def get_stats_history(self, user_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """Get historical statistics for a user over the specified number of days."""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute('''
                    SELECT
                        total_scanned,
                        total_unsubscribed,
                        time_saved,
                        emails_deleted,
                        recorded_at
                    FROM stats_history
                    WHERE user_id = ?
                    AND recorded_at >= datetime('now', '-' || ? || ' days')
                    ORDER BY recorded_at ASC
                ''', (user_id, days))

                history = []
                for row in cursor:
                    history.append({
                        'total_scanned': row['total_scanned'],
                        'total_unsubscribed': row['total_unsubscribed'],
                        'time_saved': row['time_saved'],
                        'emails_deleted': row['emails_deleted'],
                        'recorded_at': row['recorded_at']
                    })

                return history
        except Exception as e:
            logger.error(f"Failed to get stats history for user {user_id}: {e}")
            return []
    
    def cleanup_old_activities(self, days_to_keep: int = 30) -> bool:
        """Clean up activities older than specified days."""
        try:
            with self.lock:
                with self.get_connection() as conn:
                    result = conn.execute('''
                        DELETE FROM user_activities
                        WHERE timestamp < datetime('now', '-{} days')
                    '''.format(days_to_keep))

                    deleted_count = result.rowcount
                    conn.commit()

                    if deleted_count > 0:
                        logger.info(f"Cleaned up {deleted_count} old activities")

                    return True

        except Exception as e:
            logger.error(f"Failed to cleanup old activities: {e}")
            return False

    def save_operation(self, user_id: str, operation_id: str, payload_dict: Dict[str, Any]) -> bool:
        """Save an operation for undo functionality.

        Args:
            user_id: User ID
            operation_id: Unique operation ID (UUID)
            payload_dict: Dictionary containing operation details

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                # Ensure user exists
                self.ensure_user_exists(user_id)

                # Convert payload to JSON
                payload_json = json.dumps(payload_dict)

                conn.execute('''
                    INSERT INTO operations_history (user_id, operation_id, payload_json)
                    VALUES (?, ?, ?)
                ''', (user_id, operation_id, payload_json))

                conn.commit()
                logger.info(f"Saved operation {operation_id} for user {user_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to save operation {operation_id}: {e}")
            return False

    def get_operation(self, user_id: str, operation_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve an operation for undo.

        Args:
            user_id: User ID
            operation_id: Operation ID to retrieve

        Returns:
            Operation payload dict or None if not found
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute('''
                    SELECT payload_json, undone
                    FROM operations_history
                    WHERE user_id = ? AND operation_id = ?
                ''', (user_id, operation_id))

                row = cursor.fetchone()
                if row:
                    payload = json.loads(row['payload_json'])
                    payload['undone'] = bool(row['undone'])
                    return payload
                else:
                    logger.warning(f"Operation {operation_id} not found for user {user_id}")
                    return None

        except Exception as e:
            logger.error(f"Failed to get operation {operation_id}: {e}")
            return None

    def mark_operation_undone(self, user_id: str, operation_id: str) -> bool:
        """Mark an operation as undone.

        Args:
            user_id: User ID
            operation_id: Operation ID to mark as undone

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                conn.execute('''
                    UPDATE operations_history
                    SET undone = 1
                    WHERE user_id = ? AND operation_id = ?
                ''', (user_id, operation_id))

                conn.commit()
                logger.info(f"Marked operation {operation_id} as undone for user {user_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to mark operation {operation_id} as undone: {e}")
            return False

    def delete_user_data(self, user_id: str) -> bool:
        """Delete all stored data for a user.

        Args:
            user_id: User ID whose data should be deleted

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with self.lock:
                with self.get_connection() as conn:
                    # Delete from all tables
                    conn.execute('DELETE FROM operations_history WHERE user_id = ?', (user_id,))
                    conn.execute('DELETE FROM domains_unsubscribed WHERE user_id = ?', (user_id,))
                    conn.execute('DELETE FROM user_activities WHERE user_id = ?', (user_id,))
                    conn.execute('DELETE FROM user_stats WHERE user_id = ?', (user_id,))
                    conn.execute('DELETE FROM users WHERE user_id = ?', (user_id,))

                    conn.commit()
                    logger.info(f"Deleted all data for user {user_id}")
                    return True

        except Exception as e:
            logger.error(f"Failed to delete data for user {user_id}: {e}")
            return False


# Global database manager instance
db_manager = None

def initialize_database(db_path: str = "gmail_unsubscriber.db") -> bool:
    """Initialize the global database manager."""
    global db_manager
    try:
        db_manager = DatabaseManager(db_path)
        success = db_manager.initialize_database()
        if success:
            logger.info("Database initialized successfully")
        else:
            logger.error("Database initialization failed")
        return success
    except Exception as e:
        logger.error(f"Failed to initialize database manager: {e}")
        return False

def get_db_manager() -> Optional[DatabaseManager]:
    """Get the global database manager instance."""
    return db_manager