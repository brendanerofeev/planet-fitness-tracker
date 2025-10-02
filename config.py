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