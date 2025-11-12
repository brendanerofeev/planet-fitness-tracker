#!/usr/bin/env python3
"""
Migration script to transfer data from SQLite to PostgreSQL
Usage: python migrate_sqlite_to_postgres.py [--sqlite-path PATH] [--postgres-url URL]
"""

import argparse
import sys
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from models import Base, Gym, CapacityLog, Credential, SyncHistory
from config import DatabaseConfig


def get_sqlite_url(sqlite_path: str = None) -> str:
    """Get SQLite database URL"""
    if sqlite_path:
        return f"sqlite:///{sqlite_path}"
    return f"sqlite:///{DatabaseConfig.get_sqlite_path()}"


def get_postgres_url(postgres_url: str = None) -> str:
    """Get PostgreSQL database URL"""
    if postgres_url:
        return postgres_url
    return DatabaseConfig.get_database_url()


def migrate_data(sqlite_url: str, postgres_url: str, drop_existing: bool = False):
    """
    Migrate data from SQLite to PostgreSQL

    Args:
        sqlite_url: SQLite database URL
        postgres_url: PostgreSQL database URL
        drop_existing: If True, drop existing PostgreSQL tables before migration
    """
    print("=" * 70)
    print("SQLite to PostgreSQL Migration Tool")
    print("=" * 70)
    print(f"Source (SQLite): {sqlite_url}")
    print(f"Target (PostgreSQL): {postgres_url.split('@')[0]}@***")  # Hide credentials
    print("=" * 70)

    # Create engines
    print("\n[1/6] Connecting to databases...")
    sqlite_engine = create_engine(sqlite_url, echo=False)
    postgres_engine = create_engine(postgres_url, echo=False)

    SQLiteSession = sessionmaker(bind=sqlite_engine)
    PostgresSession = sessionmaker(bind=postgres_engine)

    sqlite_session = SQLiteSession()
    postgres_session = PostgresSession()

    try:
        # Test connections
        sqlite_session.execute(text("SELECT 1"))
        postgres_session.execute(text("SELECT 1"))
        print("✓ Successfully connected to both databases")

        # Drop existing tables if requested
        if drop_existing:
            print("\n[2/6] Dropping existing PostgreSQL tables...")
            Base.metadata.drop_all(bind=postgres_engine)
            print("✓ Existing tables dropped")
        else:
            print("\n[2/6] Keeping existing PostgreSQL tables...")

        # Create tables in PostgreSQL
        print("\n[3/6] Creating tables in PostgreSQL...")
        Base.metadata.create_all(bind=postgres_engine)
        print("✓ Tables created")

        # Migrate Gyms
        print("\n[4/6] Migrating gyms...")
        gyms = sqlite_session.query(Gym).all()
        print(f"  Found {len(gyms)} gyms to migrate")

        gym_id_mapping = {}  # Map old IDs to new IDs
        for gym in gyms:
            # Check if gym already exists
            existing = postgres_session.query(Gym).filter(
                Gym.club_name == gym.club_name
            ).first()

            if existing:
                gym_id_mapping[gym.id] = existing.id
                print(f"  - Skipping existing gym: {gym.club_name}")
            else:
                new_gym = Gym(
                    club_name=gym.club_name,
                    club_address=gym.club_address,
                    created_at=gym.created_at
                )
                postgres_session.add(new_gym)
                postgres_session.flush()  # Get the new ID
                gym_id_mapping[gym.id] = new_gym.id
                print(f"  - Migrated: {gym.club_name}")

        postgres_session.commit()
        print(f"✓ Migrated {len(gym_id_mapping)} gyms")

        # Migrate Capacity Logs
        print("\n[5/6] Migrating capacity logs...")
        capacity_logs = sqlite_session.query(CapacityLog).all()
        print(f"  Found {len(capacity_logs)} capacity logs to migrate")

        batch_size = 1000
        migrated_count = 0

        for i in range(0, len(capacity_logs), batch_size):
            batch = capacity_logs[i:i + batch_size]

            for log in batch:
                # Use mapped gym_id
                new_gym_id = gym_id_mapping.get(log.gym_id)
                if not new_gym_id:
                    print(f"  ! Warning: Skipping log for unknown gym_id {log.gym_id}")
                    continue

                new_log = CapacityLog(
                    gym_id=new_gym_id,
                    users_count=log.users_count,
                    users_limit=log.users_limit,
                    timestamp=log.timestamp,
                    created_at=log.created_at
                )
                postgres_session.add(new_log)
                migrated_count += 1

            postgres_session.commit()
            print(f"  - Progress: {migrated_count}/{len(capacity_logs)} logs migrated")

        print(f"✓ Migrated {migrated_count} capacity logs")

        # Migrate Credentials
        print("\n[6/6] Migrating credentials and sync history...")
        credentials = sqlite_session.query(Credential).all()
        print(f"  Found {len(credentials)} credentials to migrate")

        for cred in credentials:
            # Check if credential already exists
            existing = postgres_session.query(Credential).first()
            if existing:
                print("  - Updating existing credentials")
                existing.email = cred.email
                existing.password = cred.password
                existing.updated_at = cred.updated_at
            else:
                new_cred = Credential(
                    email=cred.email,
                    password=cred.password,
                    created_at=cred.created_at,
                    updated_at=cred.updated_at
                )
                postgres_session.add(new_cred)
                print("  - Migrated credentials")

        postgres_session.commit()

        # Migrate Sync History
        sync_history = sqlite_session.query(SyncHistory).all()
        print(f"  Found {len(sync_history)} sync history entries to migrate")

        for sync in sync_history:
            new_sync = SyncHistory(
                started_at=sync.started_at,
                completed_at=sync.completed_at,
                status=sync.status,
                gyms_fetched=sync.gyms_fetched,
                error_message=sync.error_message,
                duration_seconds=sync.duration_seconds,
                triggered_by=sync.triggered_by
            )
            postgres_session.add(new_sync)

        postgres_session.commit()
        print(f"✓ Migrated {len(sync_history)} sync history entries")

        # Summary
        print("\n" + "=" * 70)
        print("Migration Summary:")
        print("=" * 70)
        print(f"  Gyms:            {len(gym_id_mapping)}")
        print(f"  Capacity Logs:   {migrated_count}")
        print(f"  Credentials:     {len(credentials)}")
        print(f"  Sync History:    {len(sync_history)}")
        print("=" * 70)
        print("✓ Migration completed successfully!")
        print("=" * 70)

    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        postgres_session.rollback()
        raise
    finally:
        sqlite_session.close()
        postgres_session.close()


def main():
    parser = argparse.ArgumentParser(
        description="Migrate data from SQLite to PostgreSQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use default paths from config
  python migrate_sqlite_to_postgres.py

  # Specify custom SQLite path
  python migrate_sqlite_to_postgres.py --sqlite-path ./my_data.db

  # Specify custom PostgreSQL URL
  python migrate_sqlite_to_postgres.py --postgres-url postgresql://user:pass@localhost/dbname

  # Drop existing PostgreSQL tables before migration
  python migrate_sqlite_to_postgres.py --drop-existing

Note: Set database configuration in .env file or environment variables
        """
    )

    parser.add_argument(
        '--sqlite-path',
        type=str,
        help='Path to SQLite database (default: from config)'
    )

    parser.add_argument(
        '--postgres-url',
        type=str,
        help='PostgreSQL connection URL (default: from config)'
    )

    parser.add_argument(
        '--drop-existing',
        action='store_true',
        help='Drop existing PostgreSQL tables before migration'
    )

    args = parser.parse_args()

    # Get database URLs
    sqlite_url = get_sqlite_url(args.sqlite_path)
    postgres_url = get_postgres_url(args.postgres_url)

    # Confirm if dropping existing data
    if args.drop_existing:
        print("WARNING: This will delete all existing data in PostgreSQL!")
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Migration cancelled.")
            sys.exit(0)

    # Run migration
    try:
        migrate_data(sqlite_url, postgres_url, args.drop_existing)
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
