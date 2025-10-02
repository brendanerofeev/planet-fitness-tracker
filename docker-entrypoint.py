#!/usr/bin/env python3
"""
Docker entrypoint script to run both scheduler and web app
"""

import os
import sys
import signal
import subprocess
import time
from threading import Thread

# Check for required environment variables
if not os.getenv('PF_EMAIL') or not os.getenv('PF_PASSWORD'):
    print("ERROR: PF_EMAIL and PF_PASSWORD environment variables must be set!")
    sys.exit(1)

print("Starting Gym Capacity Logger Container...")

# Create necessary directories
os.makedirs('/app/data', exist_ok=True)
os.makedirs('/app/logs', exist_ok=True)

# Process list
processes = []

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print("\nShutting down services...")
    for p in processes:
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
    print("Services stopped.")
    sys.exit(0)

# Set up signal handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# Start the scheduler
print("Starting data logger with scheduler...")
scheduler_process = subprocess.Popen([sys.executable, 'scheduler.py'])
processes.append(scheduler_process)

# Give scheduler a moment to start
time.sleep(2)

# Start the Flask web application
print(f"Starting Flask web dashboard on port {os.getenv('FLASK_PORT', '5000')}...")
flask_process = subprocess.Popen([sys.executable, 'web_app.py'])
processes.append(flask_process)

# Monitor processes
try:
    while True:
        # Check if any process has died
        for p in processes:
            if p.poll() is not None:
                print(f"Process exited with code {p.returncode}")
                signal_handler(None, None)
        time.sleep(1)
except KeyboardInterrupt:
    signal_handler(None, None)