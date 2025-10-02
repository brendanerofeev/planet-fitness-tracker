#!/usr/bin/env python3
"""
Planet Fitness Gym Capacity Logger

This script logs into Planet Fitness and tracks gym capacity metrics
for historical analysis to determine optimal workout times.
"""

import requests
import json
import csv
import os
from datetime import datetime
from typing import Dict, List, Optional
import time
import sys
import config
from database import GymDatabase


class PlanetFitnessLogger:
    def __init__(self):
        self.base_url = "https://planetfitness.perfectgym.com.au/clientportal2"
        self.session = requests.Session()
        self.jwt_token = None
        self.max_retries = config.MAX_RETRIES
        self.retry_delay = config.RETRY_DELAY
        
        # Headers based on the captured request
        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-US,en;q=0.9,en-AU;q=0.8",
            "Content-Type": "application/json;charset=UTF-8",
            "cp-lang": "en",
            "cp-mode": "desktop",
            "Origin": "https://planetfitness.perfectgym.com.au",
            "Referer": "https://planetfitness.perfectgym.com.au/clientportal2/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0",
            "X-Requested-With": "XMLHttpRequest"
        }
        
        # Data storage 
        self.json_file = config.JSON_FILE
        self.csv_file = config.CSV_FILE
        self.db = GymDatabase()
        
    def login(self, email: str, password: str) -> bool:
        """
        Login to Planet Fitness and obtain JWT token
        
        Args:
            email: User email
            password: User password
            
        Returns:
            bool: True if login successful, False otherwise
        """
        login_url = f"{self.base_url}/Auth/Login"
        
        payload = {
            "RememberMe": False,
            "Login": email,
            "Password": password
        }
        
        for attempt in range(self.max_retries):
            try:
                print(f"Login attempt {attempt + 1}/{self.max_retries}")
                response = self.session.post(
                    login_url,
                    headers=self.headers,
                    json=payload,
                    timeout=config.TIMEOUT
                )
                
                if response.status_code == 200:
                    # Extract JWT token from response headers
                    self.jwt_token = response.headers.get('jwt-token')
                    if self.jwt_token:
                        print(f"Login successful! Token obtained.")
                        return True
                    else:
                        print("Login failed: No JWT token received")
                        print(f"Response: {response.text[:200]}")
                        return False
                else:
                    print(f"Login failed: HTTP {response.status_code}")
                    print(f"Response: {response.text[:200]}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue
                    return False
                    
            except requests.exceptions.Timeout:
                print(f"Login timeout on attempt {attempt + 1}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
            except requests.exceptions.ConnectionError as e:
                print(f"Connection error on attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
            except Exception as e:
                print(f"Login error on attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
        
        print("All login attempts failed")
        return False
    
    def get_gym_capacity_data(self) -> Optional[List[Dict]]:
        """
        Fetch current gym capacity data for all clubs
        
        Returns:
            List of gym data or None if failed
        """
        if not self.jwt_token:
            print("No JWT token available. Please login first.")
            return None
            
        capacity_url = f"{self.base_url}/Clubs/Clubs/GetMembersInClubs"
        
        # Add authorization header
        auth_headers = self.headers.copy()
        auth_headers["Authorization"] = f"Bearer {self.jwt_token}"
        
        for attempt in range(self.max_retries):
            try:
                print(f"Fetching capacity data attempt {attempt + 1}/{self.max_retries}")
                response = self.session.post(
                    capacity_url,
                    headers=auth_headers,
                    timeout=config.TIMEOUT
                )
                
                if response.status_code == 200:
                    data = response.json()
                    gym_list = data.get('UsersInClubList', [])
                    print(f"Successfully retrieved data for {len(gym_list)} gyms")
                    return gym_list
                elif response.status_code == 401:
                    print("Authentication failed - JWT token may be expired")
                    return None
                else:
                    print(f"Failed to fetch capacity data: HTTP {response.status_code}")
                    print(f"Response: {response.text[:200]}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue
                    return None
                    
            except requests.exceptions.Timeout:
                print(f"Capacity data fetch timeout on attempt {attempt + 1}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
            except requests.exceptions.ConnectionError as e:
                print(f"Connection error on attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
            except Exception as e:
                print(f"Error fetching capacity data on attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
        
        print("All capacity data fetch attempts failed")
        return None
    
    def save_data(self, gym_data: List[Dict]) -> None:
        """
        Save gym capacity data to SQLite database and backup files
        
        Args:
            gym_data: List of gym capacity data
        """
        timestamp = datetime.now().isoformat()
        
        # Save to SQLite database (primary storage)
        self.db.insert_capacity_data(gym_data, timestamp)
        
        # Prepare data with timestamp for backup files
        data_entry = {
            "timestamp": timestamp,
            "data": gym_data
        }
        
        # Save to JSON (backup)
        self._save_to_json(data_entry)
        
        # Save to CSV (backup)
        self._save_to_csv(timestamp, gym_data)
        
        print(f"Data saved for {len(gym_data)} gyms at {timestamp}")
        print(f"✓ Stored in SQLite database")
        print(f"✓ Backed up to JSON and CSV files")
    
    def _save_to_json(self, data_entry: Dict) -> None:
        """Save data to JSON file"""
        try:
            # Load existing data or create new list
            if os.path.exists(self.json_file):
                with open(self.json_file, 'r') as f:
                    all_data = json.load(f)
            else:
                all_data = []
            
            # Append new data
            all_data.append(data_entry)
            
            # Save back to file
            with open(self.json_file, 'w') as f:
                json.dump(all_data, f, indent=2)
                
        except Exception as e:
            print(f"Error saving to JSON: {e}")
    
    def _save_to_csv(self, timestamp: str, gym_data: List[Dict]) -> None:
        """Save data to CSV file"""
        try:
            # Check if CSV exists to determine if we need headers
            file_exists = os.path.exists(self.csv_file)
            
            with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
                fieldnames = ['timestamp', 'club_name', 'club_address', 'users_limit', 'users_count']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                
                # Write header if new file
                if not file_exists:
                    writer.writeheader()
                
                # Write data for each gym
                for gym in gym_data:
                    writer.writerow({
                        'timestamp': timestamp,
                        'club_name': gym.get('ClubName', ''),
                        'club_address': gym.get('ClubAddress', ''),
                        'users_limit': gym.get('UsersLimit', ''),
                        'users_count': gym.get('UsersCountCurrentlyInClub', 0)
                    })
                    
        except Exception as e:
            print(f"Error saving to CSV: {e}")
    
    def run_data_collection(self, email: str, password: str, triggered_by: str = 'scheduler') -> bool:
        """
        Complete data collection workflow

        Args:
            email: User email
            password: User password
            triggered_by: Source of the sync ('scheduler' or 'manual')

        Returns:
            bool: True if successful, False otherwise
        """
        print("Starting gym capacity data collection...")

        # Start sync logging
        sync_id = self.db.start_sync(triggered_by=triggered_by)
        gyms_fetched = 0
        error_msg = None

        try:
            # Login
            if not self.login(email, password):
                error_msg = "Login failed"
                self.db.complete_sync(sync_id, success=False, gyms_fetched=0, error_message=error_msg)
                return False

            # Get capacity data
            gym_data = self.get_gym_capacity_data()
            if not gym_data:
                error_msg = "Failed to fetch gym data"
                self.db.complete_sync(sync_id, success=False, gyms_fetched=0, error_message=error_msg)
                return False

            gyms_fetched = len(gym_data)

            # Save data
            self.save_data(gym_data)

            print(f"Data collection completed successfully! Fetched {gyms_fetched} gyms")

            # Log successful sync
            self.db.complete_sync(sync_id, success=True, gyms_fetched=gyms_fetched)
            return True

        except Exception as e:
            error_msg = str(e)
            print(f"Error during data collection: {error_msg}")
            self.db.complete_sync(sync_id, success=False, gyms_fetched=gyms_fetched, error_message=error_msg)
            return False


def main():
    """Main function to run the gym capacity logger"""
    logger = PlanetFitnessLogger()
    
    success = logger.run_data_collection(config.EMAIL, config.PASSWORD)
    
    if success:
        print("✅ Gym capacity logging completed successfully!")
    else:
        print("❌ Gym capacity logging failed!")
        exit(1)


if __name__ == "__main__":
    main()