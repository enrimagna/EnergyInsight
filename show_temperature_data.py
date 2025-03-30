#!/usr/bin/env python3
"""
Script to fetch and display the last temperature value of the day from Home Assistant 
for a specified day using the sensor.temperatura_esterna_media sensor.
By default, it shows data for yesterday.
"""

import os
import sys
import argparse
import logging
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from app.db.models import Database

# Configure logging - use a custom formatter to prevent output issues
class CustomFormatter(logging.Formatter):
    def format(self, record):
        # Ensure the message doesn't contain newlines or excessive spaces
        if record.msg:
            record.msg = record.msg.replace('\n', ' ').strip()
        return super().format(record)

# Configure logging
handler = logging.StreamHandler()
handler.setFormatter(CustomFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(handler)
# Remove the root handler to avoid duplicate messages
logger.propagate = False

# Simplified HomeAssistantFetcher class to avoid importing from app.data_fetchers
class HomeAssistantFetcher:
    """Fetches temperature data from Home Assistant."""
    
    def __init__(self, hass_url, hass_token, db=None):
        self.hass_url = hass_url
        self.hass_token = hass_token
        self.db = db if db else Database()
        
    def fetch_data_for_date(self, target_date):
        """Fetch historical outdoor temperature data from Home Assistant for a specific date."""
        try:
            # Convert date to start and end timestamps for the entire day
            start_time = datetime.combine(target_date, datetime.min.time())
            end_time = datetime.combine(target_date, datetime.max.time())
            
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
            
            # Parameters for the request - updated to use the new sensor
            params = {
                "filter_entity_id": "sensor.temperatura_esterna_media",
                "end_time": end_timestamp
            }
            
            # Make request to Home Assistant API
            try:
                logger.info(f"Fetching temperature history for {target_date} from Home Assistant")
                response = requests.get(api_url, headers=headers, params=params, timeout=15)
                response.raise_for_status()
            except (requests.exceptions.RequestException, requests.exceptions.ConnectionError) as e:
                logger.error(f"Could not connect to Home Assistant: {str(e)}")
                return False
            
            # Parse response - history API returns a list of lists
            history_data = response.json()
            
            if not history_data or len(history_data) == 0:
                logger.error(f"No history data returned for {target_date}")
                return False
                
            # The first list should contain our entity's data
            entity_history = history_data[0]
            
            if not entity_history:
                logger.error(f"No temperature data found for {target_date}")
                return False
                
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
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        
                        # Update last reading if this is more recent
                        if last_timestamp is None or timestamp > last_timestamp:
                            last_reading = temp
                            last_timestamp = timestamp
                except (ValueError, KeyError, TypeError) as e:
                    logger.warning(f"Error processing temperature reading: {str(e)}")
                    continue
            
            if last_reading is None:
                logger.error(f"No valid temperature readings found for {target_date}")
                return False
                
            # Store the last reading in the database
            self.db.add_temperature_data(last_timestamp, last_reading)
            logger.info(f"Stored last temperature reading for {target_date}: {last_reading}°C at {last_timestamp}")
            return True
                
        except Exception as e:
            logger.error(f"Error fetching temperature history: {str(e)}")
            return False

    def fetch_current_temperature(self):
        """Fetch current temperature from Home Assistant."""
        try:
            # API endpoint for getting the current state - updated to use the new sensor
            api_url = f"{self.hass_url}/api/states/sensor.temperatura_esterna_media"
            
            # Headers with authorization token
            headers = {
                "Authorization": f"Bearer {self.hass_token}",
                "Content-Type": "application/json"
            }
            
            # Make request to Home Assistant API
            try:
                logger.info("Fetching current temperature from Home Assistant")
                response = requests.get(api_url, headers=headers, timeout=10)
                response.raise_for_status()
            except (requests.exceptions.RequestException, requests.exceptions.ConnectionError) as e:
                logger.error(f"Could not connect to Home Assistant: {str(e)}")
                return None
            
            # Parse response
            entity = response.json()
            
            try:
                temp = float(entity['state'])
                logger.info(f"Current temperature: {temp}°C")
                return temp
            except (ValueError, KeyError) as e:
                logger.error(f"Error processing temperature data: {str(e)}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching current temperature: {str(e)}")
            return None

def parse_date(date_str):
    """Parse date string in YYYY-MM-DD format."""
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")

def get_last_temperature(db, date):
    """Get the last temperature reading for the specified date."""
    # Get temperature data for the specified date
    temp_data = db.get_temperature_data(date, date)
    
    if not temp_data:
        logger.warning(f"No temperature data found for date: {date}")
        return None, None
    
    # Find the latest reading
    latest_temp = None
    latest_timestamp = None
    
    for row in temp_data:
        if row['outdoor_temp'] is not None:
            # Convert date to datetime if it's a string
            if isinstance(row['date'], str):
                try:
                    timestamp = datetime.fromisoformat(row['date'])
                except ValueError:
                    # Try parsing with different format
                    try:
                        timestamp = datetime.strptime(row['date'], '%Y-%m-%d')
                    except ValueError:
                        continue
            else:
                timestamp = row['date']
            
            # Update latest reading if this is more recent
            if latest_timestamp is None or timestamp > latest_timestamp:
                latest_temp = row['outdoor_temp']
                latest_timestamp = timestamp
    
    if latest_temp is None:
        logger.warning(f"No valid temperature readings found for date: {date}")
        return None, None
    
    logger.info(f"Found last temperature reading for date: {date} - {latest_temp}°C at {latest_timestamp}")
    return latest_temp, latest_timestamp

def fetch_from_home_assistant(hass_url, hass_token, db, date):
    """Fetch temperature data from Home Assistant for the specified date."""
    fetcher = HomeAssistantFetcher(hass_url, hass_token, db)
    
    # Check if we already have data for this date
    temp_data = db.get_temperature_data(date, date)
    if temp_data and not args.force:
        logger.info(f"Found existing temperature data in database for date: {date}")
        return True, "database"
    
    # If no data exists or force refresh, try to fetch historical data
    success = fetcher.fetch_data_for_date(date)
    
    if success:
        return True, "home_assistant"
    
    # If today and no historical data, try to get current temperature
    if not success and date == datetime.now().date():
        logger.info("Trying to fetch current temperature for today")
        current_temp = fetcher.fetch_current_temperature()
        if current_temp is not None:
            # Store the current temperature
            db.add_temperature_data(datetime.now(), current_temp)
            logger.info(f"Stored current temperature: {current_temp}°C")
            return True, "home_assistant_current"
    
    # If we have existing data but couldn't fetch new data, still return success
    if temp_data:
        logger.warning(f"Could not fetch new data from Home Assistant for {date}, using existing database data")
        return True, "database"
        
    return False, None

def main():
    """Main function to run the script."""
    # Load environment variables
    load_dotenv()
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Show the last temperature reading for a specific day')
    parser.add_argument('--date', type=parse_date, 
                        default=(datetime.now() - timedelta(days=1)).date(),
                        help='Date to show data for (YYYY-MM-DD format). Default: yesterday')
    parser.add_argument('--force', action='store_true',
                        help='Force fetching new data even if data already exists')
    parser.add_argument('--current', action='store_true',
                        help='Show current temperature instead of historical data')
    parser.add_argument('--verify', action='store_true',
                        help='Verify if Home Assistant has data for the specified date')
    global args
    args = parser.parse_args()
    
    date = args.date
    force_fetch = args.force
    show_current = args.current
    verify_data = args.verify
    
    # Get Home Assistant connection details from environment
    hass_url = os.getenv('HASS_URL')
    hass_token = os.getenv('HASS_TOKEN')
    
    if not hass_url or not hass_token:
        logger.error("Home Assistant URL or token not found in environment variables")
        logger.info("Please set HASS_URL and HASS_TOKEN in your .env file")
        sys.exit(1)
    
    # Initialize database
    db = Database()
    
    # If showing current temperature, handle that separately
    if show_current:
        fetcher = HomeAssistantFetcher(hass_url, hass_token, db)
        current_temp = fetcher.fetch_current_temperature()
        
        if current_temp is not None:
            print(f"\nCurrent Temperature: {current_temp:.1f}°C")
        else:
            print("\nFailed to fetch current temperature")
            
        db.close_connection()
        sys.exit(0)
    
    # If verifying data availability, check with Home Assistant
    if verify_data:
        fetcher = HomeAssistantFetcher(hass_url, hass_token, db)
        
        # Convert date to start and end timestamps for the entire day
        start_time = datetime.combine(date, datetime.min.time())
        end_time = datetime.combine(date, datetime.max.time())
        
        # Format timestamps for Home Assistant API
        start_timestamp = start_time.isoformat()
        end_timestamp = end_time.isoformat()
        
        # API endpoint for getting history data
        api_url = f"{hass_url}/api/history/period/{start_timestamp}"
        
        # Headers with authorization token
        headers = {
            "Authorization": f"Bearer {hass_token}",
            "Content-Type": "application/json"
        }
        
        # Parameters for the request
        params = {
            "filter_entity_id": "sensor.temperatura_esterna_media",
            "end_time": end_timestamp
        }
        
        try:
            print(f"\nVerifying data availability for {date}...")
            response = requests.get(api_url, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            
            # Parse response
            history_data = response.json()
            
            if not history_data or len(history_data) == 0 or not history_data[0]:
                print(f"No data available in Home Assistant for {date}")
            else:
                readings_count = len(history_data[0])
                print(f"Found {readings_count} readings in Home Assistant for {date}")
                
                # Show a sample of readings
                if readings_count > 0:
                    print("\nSample readings:")
                    for i, reading in enumerate(history_data[0][:5]):  # Show up to 5 readings
                        state = reading.get('state', 'unknown')
                        timestamp = reading.get('last_changed', 'unknown')
                        print(f"  {timestamp}: {state}")
                        
                    if readings_count > 5:
                        print(f"  ... and {readings_count - 5} more readings")
        except Exception as e:
            print(f"Error verifying data: {str(e)}")
        
        db.close_connection()
        sys.exit(0)
    
    # Check if we need to force a new fetch
    if force_fetch:
        logger.info(f"Forcing fetch of new temperature data for date: {date}")
        # Delete existing data for this date
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM temperature_data WHERE date >= ? AND date < ?', 
                      (date, date + timedelta(days=1)))
        conn.commit()
    
    # Fetch data from Home Assistant if needed
    fetch_result, data_source = fetch_from_home_assistant(hass_url, hass_token, db, date)
    
    if not fetch_result:
        print(f"\nNo temperature data available for {date}")
        db.close_connection()
        sys.exit(1)
    
    # Get the last temperature reading
    last_temp, last_timestamp = get_last_temperature(db, date)
    
    # Display results
    print(f"\nTemperature Data for {date}:")
    print("-" * 40)
    
    if last_temp is not None:
        print(f"Last Temperature Reading: {last_temp:.1f}°C")
        if last_timestamp:
            time_str = last_timestamp.strftime('%H:%M:%S') if isinstance(last_timestamp, datetime) else "Unknown time"
            print(f"Time: {time_str}")
        
        # Show the data source
        if data_source == "database":
            print("Source: Database (previously stored data)")
        elif data_source == "home_assistant":
            print("Source: Home Assistant (historical data)")
        elif data_source == "home_assistant_current":
            print("Source: Home Assistant (current reading)")
    else:
        print("No temperature data available")
    
    print("-" * 40)
    
    # Close database connection
    db.close_connection()

if __name__ == "__main__":
    main()
