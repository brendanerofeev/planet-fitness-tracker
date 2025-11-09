# SQLite to PostgreSQL Migration Guide

This guide provides step-by-step instructions for migrating your Planet Fitness Tracker from SQLite to PostgreSQL.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Migration Options](#migration-options)
- [Option 1: Docker Migration (Recommended)](#option-1-docker-migration-recommended)
- [Option 2: Local Migration](#option-2-local-migration)
- [Verification](#verification)
- [Rollback](#rollback)
- [Troubleshooting](#troubleshooting)

## Overview

The application now supports both SQLite and PostgreSQL databases. This migration is **optional** - you can continue using SQLite if you prefer. PostgreSQL offers better performance, concurrency, and scalability for production deployments.

### What's New

- **SQLAlchemy ORM**: Database abstraction layer supporting both SQLite and PostgreSQL
- **Alembic Migrations**: Version control for database schema changes
- **Docker PostgreSQL**: PostgreSQL service in docker-compose.yml
- **Migration Script**: Automated data transfer from SQLite to PostgreSQL
- **Configuration**: Environment-based database selection

## Prerequisites

### For Docker Migration

- Docker and Docker Compose installed
- Existing SQLite database at `./data/gym_capacity.db`

### For Local Migration

- Python 3.8 or higher
- PostgreSQL 12 or higher installed locally
- Python dependencies: `pip install -r requirements.txt`

## Migration Options

You can migrate using Docker (recommended) or locally.

## Option 1: Docker Migration (Recommended)

### Step 1: Update Environment Configuration

Create or update your `.env` file:

```bash
# Copy example if you don't have .env yet
cp .env.example .env

# Edit .env and add database configuration
nano .env
```

Add these lines to `.env`:

```env
# Set to 'postgresql' to use PostgreSQL
DB_TYPE=postgresql

# PostgreSQL Configuration
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=gym_capacity
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password_here
```

**Important**: Change `your_secure_password_here` to a strong password!

### Step 2: Start PostgreSQL Service

```bash
# Start PostgreSQL only (app will fail without migrated data)
docker-compose up -d postgres

# Wait for PostgreSQL to be ready (about 10 seconds)
docker-compose logs postgres
```

You should see "database system is ready to accept connections"

### Step 3: Run Migration Script

```bash
# Run migration using Docker
docker-compose run --rm planet-fitness-tracker python migrate_sqlite_to_postgres.py

# Or run directly if dependencies are installed locally
python migrate_sqlite_to_postgres.py
```

The migration script will:
1. Connect to both databases
2. Create PostgreSQL tables
3. Copy all gyms
4. Copy all capacity logs (with progress indicator)
5. Copy credentials and sync history
6. Display a summary

### Step 4: Enable PostgreSQL Dependency (Optional)

If you want the app to wait for PostgreSQL to be ready before starting, edit `docker-compose.yml`:

```yaml
# Uncomment these lines:
depends_on:
  postgres:
    condition: service_healthy
```

### Step 5: Restart Application

```bash
# Restart with PostgreSQL
docker-compose down
docker-compose up -d

# Check logs
docker-compose logs -f planet-fitness-tracker
```

### Step 6: Verify Migration

See [Verification](#verification) section below.

## Option 2: Local Migration

### Step 1: Install PostgreSQL

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
```

**macOS:**
```bash
brew install postgresql@16
brew services start postgresql@16
```

**Windows:**
Download from https://www.postgresql.org/download/windows/

### Step 2: Create Database and User

```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Create database and user
CREATE DATABASE gym_capacity;
CREATE USER gym_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE gym_capacity TO gym_user;

# Exit
\q
```

### Step 3: Update Environment Configuration

```bash
# Create .env file
cp .env.example .env

# Edit configuration
nano .env
```

Add these lines:

```env
DB_TYPE=postgresql
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=gym_capacity
POSTGRES_USER=gym_user
POSTGRES_PASSWORD=your_secure_password
```

### Step 4: Install Python Dependencies

```bash
pip install -r requirements.txt
```

### Step 5: Run Migration

```bash
# Run migration script
python migrate_sqlite_to_postgres.py

# Or with custom paths
python migrate_sqlite_to_postgres.py --sqlite-path ./data/gym_capacity.db
```

### Step 6: Start Application

```bash
python gym_capacity_logger.py
```

## Verification

After migration, verify your data:

### 1. Check Database Type

Visit `http://localhost:5000` and the app should be running.

### 2. Verify Data Counts

```python
# Using Python
from db_sqlalchemy import GymDatabase

db = GymDatabase()
stats = db.get_capacity_stats()
gyms = db.get_all_gyms()

print(f"Total gyms: {len(gyms)}")
print(f"Total records: {stats['total_records']}")
print(f"Stats: {stats}")
```

### 3. Compare with SQLite

```bash
# Check SQLite record count
sqlite3 ./data/gym_capacity.db "SELECT COUNT(*) FROM capacity_logs;"

# Check PostgreSQL record count (Docker)
docker-compose exec postgres psql -U postgres -d gym_capacity -c "SELECT COUNT(*) FROM capacity_logs;"

# Check PostgreSQL record count (Local)
psql -U gym_user -d gym_capacity -c "SELECT COUNT(*) FROM capacity_logs;"
```

### 4. Test API Endpoints

```bash
# Get all gyms
curl http://localhost:5000/api/gyms | jq

# Get latest capacity
curl http://localhost:5000/api/capacity/latest | jq

# Get gym history
curl "http://localhost:5000/api/capacity/history?gym=BETHANIA&days=7" | jq
```

## Rollback

If you need to revert to SQLite:

### Docker Rollback

```bash
# 1. Stop containers
docker-compose down

# 2. Edit .env
nano .env

# 3. Change DB_TYPE back to sqlite
DB_TYPE=sqlite

# 4. Restart
docker-compose up -d
```

### Local Rollback

```bash
# Edit .env
nano .env

# Change DB_TYPE
DB_TYPE=sqlite

# Restart app
python gym_capacity_logger.py
```

Your SQLite database is unchanged and still contains all data.

## Troubleshooting

### Connection Refused

**Problem**: Can't connect to PostgreSQL

**Solution**:
```bash
# Check if PostgreSQL is running
docker-compose ps postgres
# or
sudo systemctl status postgresql

# Check PostgreSQL logs
docker-compose logs postgres
```

### Authentication Failed

**Problem**: Password authentication failed

**Solution**:
- Verify password in `.env` matches PostgreSQL configuration
- Check POSTGRES_PASSWORD in docker-compose.yml
- Ensure no spaces around the `=` in .env

### Migration Script Fails

**Problem**: Migration script errors

**Solution**:
```bash
# Run with drop-existing to start fresh
python migrate_sqlite_to_postgres.py --drop-existing

# Check both databases are accessible
python -c "from db_sqlalchemy import GymDatabase; db = GymDatabase(); print('OK')"
```

### Slow Migration

**Problem**: Migration takes too long

**Solution**: This is normal for large datasets. The script processes logs in batches of 1000 and shows progress. For 100,000 records, expect 2-5 minutes.

### Port Already in Use

**Problem**: Port 5432 already in use

**Solution**:
```bash
# Change PostgreSQL port in docker-compose.yml
ports:
  - "5433:5432"  # Use 5433 on host

# Update .env
POSTGRES_PORT=5433
```

### Missing Dependencies

**Problem**: `ModuleNotFoundError: No module named 'sqlalchemy'`

**Solution**:
```bash
pip install -r requirements.txt
```

## Advanced Options

### Custom Migration

```bash
# Migrate specific SQLite database
python migrate_sqlite_to_postgres.py --sqlite-path /path/to/custom.db

# Migrate to custom PostgreSQL
python migrate_sqlite_to_postgres.py --postgres-url postgresql://user:pass@host:port/db

# Drop and recreate tables
python migrate_sqlite_to_postgres.py --drop-existing
```

### Manual Migration Using Alembic

```bash
# Create database schema using Alembic
alembic upgrade head

# Then copy data manually or use migration script
```

### Dual Database Setup

You can run both databases simultaneously:

```env
# SQLite for local development
DB_TYPE=sqlite

# PostgreSQL for production (separate .env.production)
DB_TYPE=postgresql
```

## Database Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_TYPE` | `sqlite` | Database type: `sqlite` or `postgresql` |
| `SQLITE_PATH` | (auto) | Custom SQLite path (optional) |
| `POSTGRES_HOST` | `localhost` | PostgreSQL host |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_DB` | `gym_capacity` | Database name |
| `POSTGRES_USER` | `postgres` | Database user |
| `POSTGRES_PASSWORD` | - | Database password |
| `DB_POOL_SIZE` | `5` | Connection pool size |
| `DB_MAX_OVERFLOW` | `10` | Max overflow connections |
| `DB_POOL_TIMEOUT` | `30` | Pool timeout (seconds) |
| `DB_ECHO_SQL` | `false` | Log all SQL queries |

### Default Paths

- **Docker SQLite**: `/app/data/gym_capacity.db`
- **Local SQLite**: `./gym_capacity.db`
- **PostgreSQL**: Configured via environment variables

## Support

If you encounter issues:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review logs: `docker-compose logs` or check `./logs/`
3. Open an issue on GitHub with:
   - Error messages
   - Migration script output
   - Database configuration (without passwords!)
   - System information

## Benefits of PostgreSQL

After migration, you'll benefit from:

- **Better Concurrency**: Multiple users/processes can write simultaneously
- **Advanced Features**: Complex queries, JSON support, full-text search
- **Scalability**: Handle millions of records efficiently
- **Reliability**: ACID compliance, point-in-time recovery
- **Performance**: Optimized for large datasets
- **Production Ready**: Industry-standard database for web applications

## Keeping SQLite

You can choose to stay with SQLite if:

- Single-user deployment
- Small dataset (< 100K records)
- Simple deployment requirements
- No concurrent writes needed

SQLite is fully supported and will continue to work perfectly for most use cases.
