"""
Configuration file for gym capacity logger
"""

import os

# Authentication credentials
# IMPORTANT: Set these as environment variables for security
# Never commit credentials to version control
EMAIL = os.getenv('PF_EMAIL', '')
PASSWORD = os.getenv('PF_PASSWORD', '')

# File settings
JSON_FILE = 'gym_capacity_data.json'
CSV_FILE = 'gym_capacity_data.csv'

# Request settings
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
TIMEOUT = 30  # seconds

# Preferred gyms to track
MY_GYMS = ['BETHANIA', 'Springwood']

# Database Configuration
# Load environment variables for database
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not required in production


class DatabaseConfig:
    """Database configuration manager - supports SQLite and PostgreSQL"""

    # Database type: 'sqlite' or 'postgresql'
    DB_TYPE = os.getenv('DB_TYPE', 'sqlite')

    # SQLite Configuration
    SQLITE_PATH = os.getenv('SQLITE_PATH', '')

    # PostgreSQL Configuration
    POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
    POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', '5432'))
    POSTGRES_DB = os.getenv('POSTGRES_DB', 'gym_capacity')
    POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', '')

    # Connection pool settings
    POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '5'))
    MAX_OVERFLOW = int(os.getenv('DB_MAX_OVERFLOW', '10'))
    POOL_TIMEOUT = int(os.getenv('DB_POOL_TIMEOUT', '30'))

    # Echo SQL queries (for debugging)
    ECHO_SQL = os.getenv('DB_ECHO_SQL', 'false').lower() == 'true'

    @classmethod
    def get_sqlite_path(cls):
        """Get SQLite database path with fallback logic"""
        if cls.SQLITE_PATH:
            return cls.SQLITE_PATH

        # Check if running in Docker (data directory exists)
        if os.path.exists('/app/data'):
            return '/app/data/gym_capacity.db'
        else:
            # Use local path
            base_dir = os.path.dirname(os.path.abspath(__file__))
            return os.path.join(base_dir, "gym_capacity.db")

    @classmethod
    def get_database_url(cls):
        """Get SQLAlchemy database URL based on configuration"""
        if cls.DB_TYPE == 'postgresql':
            return (
                f"postgresql+psycopg2://{cls.POSTGRES_USER}:{cls.POSTGRES_PASSWORD}"
                f"@{cls.POSTGRES_HOST}:{cls.POSTGRES_PORT}/{cls.POSTGRES_DB}"
            )
        else:
            # SQLite
            sqlite_path = cls.get_sqlite_path()
            return f"sqlite:///{sqlite_path}"

    @classmethod
    def get_engine_args(cls):
        """Get SQLAlchemy engine arguments based on database type"""
        args = {
            'echo': cls.ECHO_SQL,
        }

        if cls.DB_TYPE == 'postgresql':
            args.update({
                'pool_size': cls.POOL_SIZE,
                'max_overflow': cls.MAX_OVERFLOW,
                'pool_timeout': cls.POOL_TIMEOUT,
                'pool_pre_ping': True,  # Verify connections before using
            })
        else:
            # SQLite specific settings
            args.update({
                'connect_args': {
                    'timeout': cls.POOL_TIMEOUT,
                    'check_same_thread': False,  # Allow multi-threaded access
                }
            })

        return args