"""
SQLAlchemy-based database implementation for gym capacity logger
Provides same interface as database.py but with SQLAlchemy ORM
Supports both SQLite and PostgreSQL
"""

import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from sqlalchemy import create_engine, func, and_, desc
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError

from models import Base, Gym, CapacityLog, Credential, SyncHistory
from config import DatabaseConfig


class GymDatabase:
    """SQLAlchemy-based gym database manager"""

    def __init__(self, db_url: str = None):
        """
        Initialize database connection

        Args:
            db_url: Database URL (if None, uses DatabaseConfig)
        """
        if db_url is None:
            db_url = DatabaseConfig.get_database_url()
            engine_args = DatabaseConfig.get_engine_args()
        else:
            engine_args = {'echo': False}

        self.engine = create_engine(db_url, **engine_args)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        # Store database URL for compatibility
        self.db_url = db_url

        # Backward compatibility: db_path property for SQLite
        if DatabaseConfig.DB_TYPE == 'sqlite':
            self.db_path = DatabaseConfig.get_sqlite_path()
        else:
            self.db_path = f"PostgreSQL: {DatabaseConfig.POSTGRES_HOST}:{DatabaseConfig.POSTGRES_PORT}/{DatabaseConfig.POSTGRES_DB}"

        # Create tables if they don't exist
        self.init_database()

    def init_database(self):
        """Initialize the database and create tables if they don't exist"""
        Base.metadata.create_all(bind=self.engine)

    def get_session(self) -> Session:
        """Get a new database session"""
        return self.SessionLocal()

    def get_or_create_gym(self, club_name: str, club_address: str) -> int:
        """Get gym ID or create new gym if it doesn't exist"""
        session = self.get_session()
        try:
            # Try to get existing gym
            gym = session.query(Gym).filter(Gym.club_name == club_name).first()

            if gym:
                return gym.id

            # Create new gym
            gym = Gym(club_name=club_name, club_address=club_address)
            session.add(gym)
            session.commit()
            session.refresh(gym)
            return gym.id

        except IntegrityError:
            # Another process may have created it
            session.rollback()
            gym = session.query(Gym).filter(Gym.club_name == club_name).first()
            return gym.id if gym else None
        finally:
            session.close()

    def insert_capacity_data(self, gym_data: List[Dict], timestamp: str = None):
        """Insert capacity data for multiple gyms"""
        if timestamp is None:
            timestamp_dt = datetime.now()
        else:
            timestamp_dt = datetime.fromisoformat(timestamp)

        session = self.get_session()
        try:
            for gym in gym_data:
                club_name = gym.get('ClubName', '')
                club_address = gym.get('ClubAddress', '')
                users_count = gym.get('UsersCountCurrentlyInClub', 0)
                users_limit = gym.get('UsersLimit')

                # Get or create gym
                gym_id = self.get_or_create_gym(club_name, club_address)

                # Insert capacity log
                capacity_log = CapacityLog(
                    gym_id=gym_id,
                    users_count=users_count,
                    users_limit=users_limit,
                    timestamp=timestamp_dt
                )
                session.add(capacity_log)

            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_latest_capacity_data(self) -> List[Dict]:
        """Get the latest capacity data for all gyms"""
        session = self.get_session()
        try:
            # Subquery to get latest timestamp for each gym
            subquery = session.query(
                CapacityLog.gym_id,
                func.max(CapacityLog.timestamp).label('max_timestamp')
            ).group_by(CapacityLog.gym_id).subquery()

            # Join to get full records
            results = session.query(
                Gym.club_name,
                Gym.club_address,
                CapacityLog.users_count,
                CapacityLog.users_limit,
                CapacityLog.timestamp
            ).join(
                CapacityLog, Gym.id == CapacityLog.gym_id
            ).join(
                subquery,
                and_(
                    CapacityLog.gym_id == subquery.c.gym_id,
                    CapacityLog.timestamp == subquery.c.max_timestamp
                )
            ).order_by(Gym.club_name).all()

            return [{
                'club_name': row[0],
                'club_address': row[1],
                'users_count': row[2],
                'users_limit': row[3],
                'timestamp': row[4].isoformat() if isinstance(row[4], datetime) else row[4]
            } for row in results]
        finally:
            session.close()

    def get_gym_history(self, club_name: str, days: int = 7) -> List[Dict]:
        """Get historical data for a specific gym"""
        session = self.get_session()
        try:
            cutoff_date = datetime.now() - timedelta(days=days)

            results = session.query(
                CapacityLog.users_count,
                CapacityLog.users_limit,
                CapacityLog.timestamp
            ).join(
                Gym, CapacityLog.gym_id == Gym.id
            ).filter(
                and_(
                    Gym.club_name == club_name,
                    CapacityLog.timestamp >= cutoff_date
                )
            ).order_by(desc(CapacityLog.timestamp)).all()

            return [{
                'users_count': row[0],
                'users_limit': row[1],
                'timestamp': row[2].isoformat() if isinstance(row[2], datetime) else row[2]
            } for row in results]
        finally:
            session.close()

    def get_gym_history_by_date_range(self, club_name: str, date_from: str, date_to: str) -> List[Dict]:
        """Get historical data for a specific gym within a date range"""
        session = self.get_session()
        try:
            # Parse dates and add time component
            date_from_dt = datetime.fromisoformat(f"{date_from} 00:00:00")
            date_to_dt = datetime.fromisoformat(f"{date_to} 23:59:59")

            results = session.query(
                CapacityLog.users_count,
                CapacityLog.users_limit,
                CapacityLog.timestamp
            ).join(
                Gym, CapacityLog.gym_id == Gym.id
            ).filter(
                and_(
                    Gym.club_name == club_name,
                    CapacityLog.timestamp.between(date_from_dt, date_to_dt)
                )
            ).order_by(desc(CapacityLog.timestamp)).all()

            return [{
                'users_count': row[0],
                'users_limit': row[1],
                'timestamp': row[2].isoformat() if isinstance(row[2], datetime) else row[2]
            } for row in results]
        finally:
            session.close()

    def get_all_gyms(self) -> List[Dict]:
        """Get list of all gyms"""
        session = self.get_session()
        try:
            gyms = session.query(Gym).order_by(Gym.club_name).all()

            return [{
                'id': gym.id,
                'club_name': gym.club_name,
                'club_address': gym.club_address,
                'created_at': gym.created_at.isoformat() if isinstance(gym.created_at, datetime) else gym.created_at
            } for gym in gyms]
        finally:
            session.close()

    def get_capacity_stats(self, days: int = 30, gym_names: List[str] = None) -> Dict:
        """Get capacity statistics for the past N days"""
        session = self.get_session()
        try:
            cutoff_date = datetime.now() - timedelta(days=days)

            query = session.query(
                func.count(CapacityLog.id).label('total_records'),
                func.count(func.distinct(CapacityLog.gym_id)).label('total_gyms'),
                func.avg(CapacityLog.users_count).label('avg_capacity'),
                func.max(CapacityLog.users_count).label('max_capacity'),
                func.min(CapacityLog.users_count).label('min_capacity')
            ).filter(CapacityLog.timestamp >= cutoff_date)

            if gym_names:
                query = query.join(Gym, CapacityLog.gym_id == Gym.id).filter(
                    Gym.club_name.in_(gym_names)
                )

            result = query.first()

            return {
                'total_records': result[0] if result[0] else 0,
                'total_gyms': result[1] if result[1] else 0,
                'avg_capacity': round(result[2], 1) if result[2] else 0,
                'max_capacity': result[3] if result[3] else 0,
                'min_capacity': result[4] if result[4] else 0,
                'days': days
            }
        finally:
            session.close()

    def migrate_from_json(self, json_file: str):
        """Migrate data from existing JSON file to database"""
        if not os.path.exists(json_file):
            print(f"JSON file {json_file} not found, skipping migration")
            return

        with open(json_file, 'r') as f:
            json_data = json.load(f)

        print(f"Migrating {len(json_data)} entries from JSON to database...")

        for entry in json_data:
            timestamp = entry.get('timestamp')
            gym_data = entry.get('data', [])

            if timestamp and gym_data:
                self.insert_capacity_data(gym_data, timestamp)

        print("Migration completed successfully!")

    def save_credentials(self, email: str, password: str) -> bool:
        """Save or update Planet Fitness credentials"""
        session = self.get_session()
        try:
            # Check if credentials already exist
            existing = session.query(Credential).first()

            if existing:
                # Update existing credentials
                existing.email = email
                existing.password = password
                existing.updated_at = datetime.now()
            else:
                # Insert new credentials
                credential = Credential(email=email, password=password)
                session.add(credential)

            session.commit()
            return True
        except Exception as e:
            session.rollback()
            print(f"Error saving credentials: {e}")
            return False
        finally:
            session.close()

    def get_credentials(self) -> Optional[Dict[str, str]]:
        """Retrieve stored Planet Fitness credentials"""
        session = self.get_session()
        try:
            credential = session.query(Credential).first()

            if credential:
                return {
                    'email': credential.email,
                    'password': credential.password
                }
            return None
        except Exception as e:
            print(f"Error retrieving credentials: {e}")
            return None
        finally:
            session.close()

    def delete_credentials(self) -> bool:
        """Delete stored credentials"""
        session = self.get_session()
        try:
            session.query(Credential).delete()
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            print(f"Error deleting credentials: {e}")
            return False
        finally:
            session.close()

    def has_credentials(self) -> bool:
        """Check if credentials are stored"""
        creds = self.get_credentials()
        return creds is not None

    def start_sync(self, triggered_by: str = 'scheduler') -> int:
        """Create a new sync history entry and return its ID"""
        session = self.get_session()
        try:
            sync = SyncHistory(
                started_at=datetime.now(),
                status='in_progress',
                triggered_by=triggered_by
            )
            session.add(sync)
            session.commit()
            session.refresh(sync)
            return sync.id
        except Exception as e:
            session.rollback()
            print(f"Error starting sync: {e}")
            return None
        finally:
            session.close()

    def complete_sync(self, sync_id: int, success: bool, gyms_fetched: int = 0, error_message: str = None):
        """Update sync history entry with completion status"""
        session = self.get_session()
        try:
            sync = session.query(SyncHistory).filter(SyncHistory.id == sync_id).first()

            if sync:
                completed_at = datetime.now()
                duration = (completed_at - sync.started_at).total_seconds()

                sync.completed_at = completed_at
                sync.status = 'success' if success else 'failed'
                sync.gyms_fetched = gyms_fetched
                sync.error_message = error_message
                sync.duration_seconds = duration

                session.commit()
        except Exception as e:
            session.rollback()
            print(f"Error completing sync: {e}")
        finally:
            session.close()

    def get_sync_history(self, limit: int = 20) -> List[Dict]:
        """Get recent sync history"""
        session = self.get_session()
        try:
            syncs = session.query(SyncHistory).order_by(
                desc(SyncHistory.started_at)
            ).limit(limit).all()

            return [{
                'id': sync.id,
                'started_at': sync.started_at.isoformat() if isinstance(sync.started_at, datetime) else sync.started_at,
                'completed_at': sync.completed_at.isoformat() if sync.completed_at and isinstance(sync.completed_at, datetime) else sync.completed_at,
                'status': sync.status,
                'gyms_fetched': sync.gyms_fetched,
                'error_message': sync.error_message,
                'duration_seconds': sync.duration_seconds,
                'triggered_by': sync.triggered_by
            } for sync in syncs]
        except Exception as e:
            print(f"Error getting sync history: {e}")
            return []
        finally:
            session.close()

    def get_last_successful_sync(self) -> Optional[Dict]:
        """Get the most recent successful sync"""
        session = self.get_session()
        try:
            sync = session.query(SyncHistory).filter(
                SyncHistory.status == 'success'
            ).order_by(
                desc(SyncHistory.completed_at)
            ).first()

            if sync:
                return {
                    'started_at': sync.started_at.isoformat() if isinstance(sync.started_at, datetime) else sync.started_at,
                    'completed_at': sync.completed_at.isoformat() if isinstance(sync.completed_at, datetime) else sync.completed_at,
                    'gyms_fetched': sync.gyms_fetched,
                    'duration_seconds': sync.duration_seconds
                }
            return None
        except Exception as e:
            print(f"Error getting last successful sync: {e}")
            return None
        finally:
            session.close()


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
