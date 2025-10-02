"""
Database module for gym capacity logger
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
import os
import time


class GymDatabase:
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Check if running in Docker (data directory exists)
            if os.path.exists('/app/data'):
                db_path = '/app/data/gym_capacity.db'
            else:
                # Use absolute path based on this script's location
                base_dir = os.path.dirname(os.path.abspath(__file__))
                db_path = os.path.join(base_dir, "gym_capacity.db")
        self.db_path = db_path
        self.timeout = 30
        self.init_database()
    
    def init_database(self):
        """Initialize the database and create tables if they don't exist"""
        with sqlite3.connect(self.db_path, timeout=self.timeout) as conn:
            cursor = conn.cursor()

            # Create gyms table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS gyms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    club_name TEXT UNIQUE NOT NULL,
                    club_address TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create capacity_logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS capacity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    gym_id INTEGER NOT NULL,
                    users_count INTEGER NOT NULL,
                    users_limit INTEGER,
                    timestamp TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (gym_id) REFERENCES gyms (id)
                )
            """)

            # Create credentials table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS credentials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    password TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create sync_history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TIMESTAMP NOT NULL,
                    completed_at TIMESTAMP,
                    status TEXT NOT NULL,
                    gyms_fetched INTEGER DEFAULT 0,
                    error_message TEXT,
                    duration_seconds REAL,
                    triggered_by TEXT DEFAULT 'scheduler'
                )
            """)

            # Create indexes for better performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_capacity_logs_timestamp
                ON capacity_logs (timestamp)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sync_history_started_at
                ON sync_history (started_at DESC)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_capacity_logs_gym_id
                ON capacity_logs (gym_id)
            """)

            conn.commit()
    
    def get_or_create_gym(self, club_name: str, club_address: str) -> int:
        """Get gym ID or create new gym if it doesn't exist"""
        retries = 3
        for attempt in range(retries):
            try:
                with sqlite3.connect(self.db_path, timeout=self.timeout) as conn:
                    cursor = conn.cursor()
                    
                    # Try to get existing gym
                    cursor.execute(
                        "SELECT id FROM gyms WHERE club_name = ?",
                        (club_name,)
                    )
                    result = cursor.fetchone()
                    
                    if result:
                        return result[0]
                    
                    # Create new gym
                    cursor.execute(
                        "INSERT OR IGNORE INTO gyms (club_name, club_address) VALUES (?, ?)",
                        (club_name, club_address)
                    )
                    
                    # Get the ID (in case another process created it)
                    cursor.execute(
                        "SELECT id FROM gyms WHERE club_name = ?",
                        (club_name,)
                    )
                    result = cursor.fetchone()
                    
                    if result:
                        return result[0]
                    
                    return cursor.lastrowid
                    
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < retries - 1:
                    print(f"Database locked, retrying in {attempt + 1} seconds...")
                    time.sleep(attempt + 1)
                    continue
                raise e
    
    def insert_capacity_data(self, gym_data: List[Dict], timestamp: str = None):
        """Insert capacity data for multiple gyms"""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        
        for gym in gym_data:
            club_name = gym.get('ClubName', '')
            club_address = gym.get('ClubAddress', '')
            users_count = gym.get('UsersCountCurrentlyInClub', 0)
            users_limit = gym.get('UsersLimit')
            
            # Get or create gym
            gym_id = self.get_or_create_gym(club_name, club_address)
            
            # Insert capacity log with retry logic
            retries = 3
            for attempt in range(retries):
                try:
                    with sqlite3.connect(self.db_path, timeout=self.timeout) as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO capacity_logs (gym_id, users_count, users_limit, timestamp)
                            VALUES (?, ?, ?, ?)
                        """, (gym_id, users_count, users_limit, timestamp))
                        conn.commit()
                        break
                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e) and attempt < retries - 1:
                        print(f"Database locked during insert, retrying in {attempt + 1} seconds...")
                        time.sleep(attempt + 1)
                        continue
                    raise e
    
    def get_latest_capacity_data(self) -> List[Dict]:
        """Get the latest capacity data for all gyms"""
        with sqlite3.connect(self.db_path, timeout=self.timeout) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    g.club_name,
                    g.club_address,
                    cl.users_count,
                    cl.users_limit,
                    cl.timestamp
                FROM gyms g
                JOIN capacity_logs cl ON g.id = cl.gym_id
                WHERE cl.timestamp = (
                    SELECT MAX(timestamp) 
                    FROM capacity_logs cl2 
                    WHERE cl2.gym_id = g.id
                )
                ORDER BY g.club_name
            """)
            
            results = cursor.fetchall()
            
            return [{
                'club_name': row[0],
                'club_address': row[1],
                'users_count': row[2],
                'users_limit': row[3],
                'timestamp': row[4]
            } for row in results]
    
    def get_gym_history(self, club_name: str, days: int = 7) -> List[Dict]:
        """Get historical data for a specific gym"""
        with sqlite3.connect(self.db_path, timeout=self.timeout) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    cl.users_count,
                    cl.users_limit,
                    cl.timestamp
                FROM gyms g
                JOIN capacity_logs cl ON g.id = cl.gym_id
                WHERE g.club_name = ?
                AND cl.timestamp >= datetime('now', '-{} days')
                ORDER BY cl.timestamp DESC
            """.format(days), (club_name,))
            
            results = cursor.fetchall()
            
            return [{
                'users_count': row[0],
                'users_limit': row[1],
                'timestamp': row[2]
            } for row in results]
    
    def get_gym_history_by_date_range(self, club_name: str, date_from: str, date_to: str) -> List[Dict]:
        """Get historical data for a specific gym within a date range"""
        with sqlite3.connect(self.db_path, timeout=self.timeout) as conn:
            cursor = conn.cursor()
            
            # Add time component to dates to ensure full day coverage
            date_from = f"{date_from} 00:00:00"
            date_to = f"{date_to} 23:59:59"
            
            cursor.execute("""
                SELECT 
                    cl.users_count,
                    cl.users_limit,
                    cl.timestamp
                FROM gyms g
                JOIN capacity_logs cl ON g.id = cl.gym_id
                WHERE g.club_name = ?
                AND cl.timestamp BETWEEN ? AND ?
                ORDER BY cl.timestamp DESC
            """, (club_name, date_from, date_to))
            
            results = cursor.fetchall()
            
            return [{
                'users_count': row[0],
                'users_limit': row[1],
                'timestamp': row[2]
            } for row in results]
    
    def get_all_gyms(self) -> List[Dict]:
        """Get list of all gyms"""
        with sqlite3.connect(self.db_path, timeout=self.timeout) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, club_name, club_address, created_at
                FROM gyms
                ORDER BY club_name
            """)
            
            results = cursor.fetchall()
            
            return [{
                'id': row[0],
                'club_name': row[1],
                'club_address': row[2],
                'created_at': row[3]
            } for row in results]
    
    def get_capacity_stats(self, days: int = 30, gym_names: List[str] = None) -> Dict:
        """Get capacity statistics for the past N days"""
        with sqlite3.connect(self.db_path, timeout=self.timeout) as conn:
            cursor = conn.cursor()
            
            if gym_names:
                placeholders = ','.join('?' * len(gym_names))
                cursor.execute(f"""
                    SELECT 
                        COUNT(*) as total_records,
                        COUNT(DISTINCT cl.gym_id) as total_gyms,
                        AVG(cl.users_count) as avg_capacity,
                        MAX(cl.users_count) as max_capacity,
                        MIN(cl.users_count) as min_capacity
                    FROM capacity_logs cl
                    JOIN gyms g ON cl.gym_id = g.id
                    WHERE cl.timestamp >= datetime('now', '-{days} days')
                    AND g.club_name IN ({placeholders})
                """, gym_names)
            else:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_records,
                        COUNT(DISTINCT gym_id) as total_gyms,
                        AVG(users_count) as avg_capacity,
                        MAX(users_count) as max_capacity,
                        MIN(users_count) as min_capacity
                    FROM capacity_logs
                    WHERE timestamp >= datetime('now', '-{} days')
                """.format(days))
            
            result = cursor.fetchone()
            
            return {
                'total_records': result[0] if result[0] else 0,
                'total_gyms': result[1] if result[1] else 0,
                'avg_capacity': round(result[2], 1) if result[2] else 0,
                'max_capacity': result[3] if result[3] else 0,
                'min_capacity': result[4] if result[4] else 0,
                'days': days
            }
    
    def migrate_from_json(self, json_file: str):
        """Migrate data from existing JSON file to SQLite"""
        if not os.path.exists(json_file):
            print(f"JSON file {json_file} not found, skipping migration")
            return
        
        with open(json_file, 'r') as f:
            json_data = json.load(f)
        
        print(f"Migrating {len(json_data)} entries from JSON to SQLite...")
        
        for entry in json_data:
            timestamp = entry.get('timestamp')
            gym_data = entry.get('data', [])
            
            if timestamp and gym_data:
                self.insert_capacity_data(gym_data, timestamp)
        
        print("Migration completed successfully!")

    def save_credentials(self, email: str, password: str) -> bool:
        """Save or update Planet Fitness credentials"""
        try:
            with sqlite3.connect(self.db_path, timeout=self.timeout) as conn:
                cursor = conn.cursor()

                # Check if credentials already exist
                cursor.execute("SELECT id FROM credentials LIMIT 1")
                existing = cursor.fetchone()

                if existing:
                    # Update existing credentials
                    cursor.execute("""
                        UPDATE credentials
                        SET email = ?, password = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (email, password, existing[0]))
                else:
                    # Insert new credentials
                    cursor.execute("""
                        INSERT INTO credentials (email, password)
                        VALUES (?, ?)
                    """, (email, password))

                conn.commit()
                return True
        except Exception as e:
            print(f"Error saving credentials: {e}")
            return False

    def get_credentials(self) -> Optional[Dict[str, str]]:
        """Retrieve stored Planet Fitness credentials"""
        try:
            with sqlite3.connect(self.db_path, timeout=self.timeout) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT email, password FROM credentials LIMIT 1")
                result = cursor.fetchone()

                if result:
                    return {
                        'email': result[0],
                        'password': result[1]
                    }
                return None
        except Exception as e:
            print(f"Error retrieving credentials: {e}")
            return None

    def delete_credentials(self) -> bool:
        """Delete stored credentials"""
        try:
            with sqlite3.connect(self.db_path, timeout=self.timeout) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM credentials")
                conn.commit()
                return True
        except Exception as e:
            print(f"Error deleting credentials: {e}")
            return False

    def has_credentials(self) -> bool:
        """Check if credentials are stored"""
        creds = self.get_credentials()
        return creds is not None

    def start_sync(self, triggered_by: str = 'scheduler') -> int:
        """Create a new sync history entry and return its ID"""
        try:
            with sqlite3.connect(self.db_path, timeout=self.timeout) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO sync_history (started_at, status, triggered_by)
                    VALUES (?, 'in_progress', ?)
                """, (datetime.now().isoformat(), triggered_by))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"Error starting sync: {e}")
            return None

    def complete_sync(self, sync_id: int, success: bool, gyms_fetched: int = 0, error_message: str = None):
        """Update sync history entry with completion status"""
        try:
            with sqlite3.connect(self.db_path, timeout=self.timeout) as conn:
                cursor = conn.cursor()

                # Get start time to calculate duration
                cursor.execute("SELECT started_at FROM sync_history WHERE id = ?", (sync_id,))
                result = cursor.fetchone()

                if result:
                    started_at = datetime.fromisoformat(result[0])
                    completed_at = datetime.now()
                    duration = (completed_at - started_at).total_seconds()

                    cursor.execute("""
                        UPDATE sync_history
                        SET completed_at = ?,
                            status = ?,
                            gyms_fetched = ?,
                            error_message = ?,
                            duration_seconds = ?
                        WHERE id = ?
                    """, (
                        completed_at.isoformat(),
                        'success' if success else 'failed',
                        gyms_fetched,
                        error_message,
                        duration,
                        sync_id
                    ))
                    conn.commit()
        except Exception as e:
            print(f"Error completing sync: {e}")

    def get_sync_history(self, limit: int = 20) -> List[Dict]:
        """Get recent sync history"""
        try:
            with sqlite3.connect(self.db_path, timeout=self.timeout) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, started_at, completed_at, status, gyms_fetched,
                           error_message, duration_seconds, triggered_by
                    FROM sync_history
                    ORDER BY started_at DESC
                    LIMIT ?
                """, (limit,))

                results = []
                for row in cursor.fetchall():
                    results.append({
                        'id': row[0],
                        'started_at': row[1],
                        'completed_at': row[2],
                        'status': row[3],
                        'gyms_fetched': row[4],
                        'error_message': row[5],
                        'duration_seconds': row[6],
                        'triggered_by': row[7]
                    })
                return results
        except Exception as e:
            print(f"Error getting sync history: {e}")
            return []

    def get_last_successful_sync(self) -> Optional[Dict]:
        """Get the most recent successful sync"""
        try:
            with sqlite3.connect(self.db_path, timeout=self.timeout) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT started_at, completed_at, gyms_fetched, duration_seconds
                    FROM sync_history
                    WHERE status = 'success'
                    ORDER BY completed_at DESC
                    LIMIT 1
                """)
                result = cursor.fetchone()

                if result:
                    return {
                        'started_at': result[0],
                        'completed_at': result[1],
                        'gyms_fetched': result[2],
                        'duration_seconds': result[3]
                    }
                return None
        except Exception as e:
            print(f"Error getting last successful sync: {e}")
            return None


if __name__ == "__main__":
    # Test the database
    db = GymDatabase()
    print("Database initialized successfully!")
    
    # Show some stats if database has data
    stats = db.get_capacity_stats()
    print(f"Database stats: {stats}")
    
    # Show all gyms
    gyms = db.get_all_gyms()
    print(f"Found {len(gyms)} gyms in database")