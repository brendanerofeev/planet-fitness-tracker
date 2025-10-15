#!/usr/bin/env python3
"""
Scheduler for gym capacity logging.
Runs the logger at specified intervals.
"""

import os
import time
import logging
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from gym_capacity_logger import PlanetFitnessLogger
from database import GymDatabase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/scheduler.log' if os.path.exists('/app/logs') else 'scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize database
db = GymDatabase()

def run_logger():
    """Run the gym capacity logger"""
    try:
        logger.info("Starting gym capacity data collection...")
        pf_logger = PlanetFitnessLogger()

        # Try to get credentials from database first, fall back to environment variables
        creds = db.get_credentials()
        if creds:
            email = creds['email']
            password = creds['password']
            logger.info(f"Using credentials from database for: {email}")
        else:
            email = os.getenv('PF_EMAIL')
            password = os.getenv('PF_PASSWORD')
            if email and password:
                logger.info("Using credentials from environment variables")

        if not email or not password or email == 'your-email@example.com':
            logger.error("No valid credentials found. Please configure credentials via Settings page or environment variables")
            return

        success = pf_logger.run_data_collection(email, password)
        if success:
            logger.info("Data collection completed successfully")
        else:
            logger.error("Data collection failed")
    except Exception as e:
        logger.error(f"Error during data collection: {e}")

def main():
    # Get interval from environment variable (in minutes)
    interval_minutes = int(os.getenv('LOG_INTERVAL', '15'))

    logger.info(f"Starting scheduler with {interval_minutes} minute interval")

    # Run immediately on startup
    logger.info("Running initial data collection...")
    run_logger()

    # Set up scheduler
    scheduler = BlockingScheduler()

    # Schedule the job
    scheduler.add_job(
        func=run_logger,
        trigger="interval",
        minutes=interval_minutes,
        id='gym_logger',
        name='Gym Capacity Logger',
        replace_existing=True,
        next_run_time=datetime.now()  # Run immediately
    )

    try:
        logger.info("Scheduler started. Press Ctrl+C to stop.")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
        scheduler.shutdown()

if __name__ == "__main__":
    main()