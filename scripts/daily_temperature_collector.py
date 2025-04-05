#!/usr/bin/env python3
"""
Script to get the last temperature reading for a specific date from Home Assistant
and update the temperature in the energy_data.db database if a row exists.
"""

import os
import argparse
import logging
import sqlite3
from datetime import datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo  # Standard library alternative to pytz
from dotenv import load_dotenv
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Database:
    """Database interface for storing temperature data."""
    
    def __init__(self, db_file=None):
        """Initialize database connection."""
        self.db_file = db_file or os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                              "app", "db", "energy_data.db")
        self.data = []  # For temporary storage
        
    def add_temperature_data(self, timestamp, temperature):
        """Store temperature data."""
        self.data.append({
            'timestamp': timestamp,
            'temperature': temperature
        })
        return True
        
    def get_temperature_data(self, start_date, end_date):
        """Retrieve temperature data for the given date range."""
        return self.data
    
    def update_temperature_in_db(self, date, temperature):
        """Update the temperature in the database for the specified date if a row exists."""
        try:
            # Format date as string (YYYY-MM-DD)
            date_str = date.strftime("%Y-%m-%d")
            
            # Connect to the SQLite database
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Check if a row exists for this date
            cursor.execute("SELECT date FROM energy_data WHERE date = ?", (date_str,))
            row = cursor.fetchone()
            
            if row:
                # Update the temperature for this date
                cursor.execute(
                    "UPDATE energy_data SET outdoor_temp = ? WHERE date = ?", 
                    (temperature, date_str)
                )
                conn.commit()
                logger.info(f"Updated temperature to {temperature}°C for date {date_str} in database")
                return True
            else:
                logger.warning(f"No row found for date {date_str} in database, temperature not updated")
                return False
                
        except sqlite3.Error as e:
            logger.error(f"Database error: {str(e)}")
            return False
        finally:
            if conn:
                conn.close()

class HomeAssistantFetcher:
    """Fetches temperature data from Home Assistant."""
    
    def __init__(self, hass_url=None, hass_token=None, db=None, local_timezone=None):
        """Initialize the Home Assistant data fetcher."""
        # Load environment variables
        load_dotenv()
        
        self.hass_url = hass_url if hass_url else os.getenv("HASS_URL")
        self.hass_token = hass_token if hass_token else os.getenv("HASS_TOKEN")
        self.db = db if db else Database()
        
        # Set local timezone
        tz_name = os.getenv("LOCAL_TIMEZONE", "Europe/Rome")
        self.local_timezone = local_timezone or ZoneInfo(tz_name)
        
        if not self.hass_url or not self.hass_token:
            raise ValueError("Home Assistant credentials not found. Please set HASS_URL and HASS_TOKEN in .env file")
        
    def fetch_data_for_date(self, target_date):
        """Fetch historical outdoor temperature data from Home Assistant for a specific date."""
        try:
            # Convert date to start and end timestamps for the entire day in local time
            start_time = datetime.combine(target_date, datetime.min.time())
            start_time = start_time.replace(tzinfo=self.local_timezone)
            
            end_time = datetime.combine(target_date, datetime.max.time())
            end_time = end_time.replace(tzinfo=self.local_timezone)
            
            # Format timestamps for Home Assistant API
            start_timestamp = start_time.isoformat()
            end_timestamp = end_time.isoformat()
            
            # API endpoint for getting history data
            api_url = f"{self.hass_url}/api/history/period/{start_timestamp}"
            
            # Headers with authorization token
            headers = {
                "Authorization": f"Bearer {self.hass_token}",
                "Content-Type": "application/json"
            }
            
            # Parameters for the request
            params = {
                "filter_entity_id": "sensor.temperatura_esterna_media",
                "end_time": end_timestamp
            }
            
            # Make request to Home Assistant API
            logger.info(f"Fetching temperature history for {target_date} from Home Assistant")
            response = requests.get(api_url, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            
            # Parse response - history API returns a list of lists
            history_data = response.json()
            
            if not history_data or len(history_data) == 0:
                logger.error(f"No history data returned for {target_date}")
                return None, None
                
            # The first list should contain our entity's data
            entity_history = history_data[0]
            
            if not entity_history:
                logger.error(f"No temperature data found for {target_date}")
                return None, None
                
            # Get the last temperature reading of the day
            last_reading = None
            last_timestamp = None
            
            # Process each state change to find the last valid reading
            for state_item in entity_history:
                try:
                    # Extract state (temperature) and timestamp
                    state = state_item.get('state')
                    if state and state.lower() != 'unknown' and state.lower() != 'unavailable':
                        temp = float(state)
                        timestamp_str = state_item.get('last_changed')
                        
                        # Parse timestamp and convert to local timezone
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        local_timestamp = timestamp.astimezone(self.local_timezone)
                        
                        # Update last reading if this is more recent
                        if last_timestamp is None or local_timestamp > last_timestamp:
                            last_reading = temp
                            last_timestamp = local_timestamp
                except (ValueError, KeyError, TypeError) as e:
                    logger.warning(f"Error processing temperature reading: {str(e)}")
                    continue
            
            if last_reading is None:
                logger.error(f"No valid temperature readings found for {target_date}")
                return None, None
                
            # Store the last reading in the database
            self.db.add_temperature_data(last_timestamp, last_reading)
            logger.info(f"Last temperature reading for {target_date}: {last_reading}°C at {last_timestamp}")
            
            # Update the temperature in the energy_data.db if a row exists
            self.db.update_temperature_in_db(target_date, last_reading)
            
            return last_reading, last_timestamp
                
        except Exception as e:
            logger.error(f"Error fetching temperature history: {str(e)}")
            return None, None

def parse_date(date_str):
    """Parse date string in YYYY-MM-DD format."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")

def main():
    """Main function to run the script."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Get the last temperature reading for a specific day')
    parser.add_argument('--date', type=parse_date, 
                        default=(datetime.now() - timedelta(days=1)).date(),
                        help='Date to show data for (YYYY-MM-DD format). Default: yesterday')
    parser.add_argument('--db-file', type=str,
                        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                            "app", "db", "energy_data.db"),
                        help='Path to the SQLite database file')
    args = parser.parse_args()
    
    date = args.date
    db_file = args.db_file
    
    # Initialize database and Home Assistant fetcher
    db = Database(db_file)
    fetcher = HomeAssistantFetcher(db=db)
    
    # Fetch and display the last temperature for the specified date
    temp, timestamp = fetcher.fetch_data_for_date(date)
    
    if temp is not None:
        print(f"Last temperature on {date}: {temp}°C at {timestamp.strftime('%H:%M:%S')} (local time)")
    else:
        print(f"No temperature data available for {date}")

if __name__ == "__main__":
    main()