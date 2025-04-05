#!/usr/bin/env python3
"""
Production-ready service to collect daily energy and temperature data.
This script is designed to run continuously in a Docker container.
It collects energy data from MELCloud and temperature data from Home Assistant,
and updates the database, ensuring one record per day with complete information.

Features:
1. Checks for missing data regularly
2. Ensures data continuity with one record per day
3. Updates the database with the latest data
4. Creates new price entries automatically each month
5. Retries failed attempts periodically
"""

import os
import sys
import time
import logging
import datetime
import argparse
from dotenv import load_dotenv
from app.db.models import Database
from daily_energy_collector import MELCloudCollector
from daily_temperature_collector import HomeAssistantFetcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("data_collector_service.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DataCollectorService:
    """Service to collect and maintain energy and temperature data."""
    
    def __init__(self, db=None, debug_mode=False):
        """Initialize the data collector service.
        
        Args:
            db: Database instance
            debug_mode: Whether to save raw API responses
        """
        # Load environment variables
        load_dotenv()
        
        # Initialize database
        self.db = db if db else Database()
        self.debug_mode = debug_mode
        
        # Initialize collectors
        try:
            self.melcloud = MELCloudCollector(debug_mode=debug_mode)
            logger.info("MELCloud collector initialized")
        except Exception as e:
            logger.error(f"Failed to initialize MELCloud collector: {e}")
            self.melcloud = None
        
        try:
            self.hass = HomeAssistantFetcher(db=self.db)
            logger.info("Home Assistant collector initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Home Assistant collector: {e}")
            self.hass = None
    
    def check_missing_data(self, days_to_check=180):
        """Check for missing or incomplete data in the last N days.
        
        Returns:
            Dictionary of dates with missing data, with type of missing data
        """
        today = datetime.date.today()
        missing_data = {}
        
        # Get the earliest date to check
        earliest_date = today - datetime.timedelta(days=days_to_check)
        
        logger.info(f"Checking for missing data from {earliest_date} to {today}")
        
        # Get all energy data in the date range
        energy_data = self.db.get_energy_data(earliest_date, today)
        
        # Create a set of dates that have energy data
        dates_with_energy_data = set()
        for row in energy_data:
            # Check if the row has actual energy data
            has_energy_data = False
            if 'total_energy_consumed' in row and row['total_energy_consumed']:
                has_energy_data = True
            
            if has_energy_data:
                # Convert to date object if it's a string
                if isinstance(row['date'], str):
                    try:
                        date = datetime.datetime.fromisoformat(row['date']).date()
                    except ValueError:
                        date = datetime.datetime.strptime(row['date'], '%Y-%m-%d').date()
                else:
                    date = row['date'].date() if isinstance(row['date'], datetime.datetime) else row['date']
                
                dates_with_energy_data.add(date)
        
        # Get all temperature data in the date range
        temp_data = self.db.get_temperature_data(earliest_date, today)
        
        # Create a set of dates that have temperature data
        dates_with_temp_data = set()
        for row in temp_data:
            if 'outdoor_temp' in row and row['outdoor_temp'] is not None:
                # Convert to date object if it's a string
                if isinstance(row['date'], str):
                    try:
                        date = datetime.datetime.fromisoformat(row['date']).date()
                    except ValueError:
                        date = datetime.datetime.strptime(row['date'], '%Y-%m-%d').date()
                else:
                    date = row['date'].date() if isinstance(row['date'], datetime.datetime) else row['date']
                
                dates_with_temp_data.add(date)
        
        # Find missing dates (excluding today and future dates)
        current_date = earliest_date
        yesterday = today - datetime.timedelta(days=1)
        
        while current_date <= yesterday:
            missing_type = []
            
            if current_date not in dates_with_energy_data:
                missing_type.append("energy")
            
            if current_date not in dates_with_temp_data:
                missing_type.append("temperature")
            
            if missing_type:
                missing_data[current_date] = missing_type
            
            current_date += datetime.timedelta(days=1)
        
        logger.info(f"Found {len(missing_data)} dates with missing data")
        return missing_data
    
    def collect_energy_data(self, target_date):
        """Collect energy data for a specific date.
        
        Args:
            target_date: The date to collect data for
            
        Returns:
            True if successful, False otherwise
        """
        if not self.melcloud:
            logger.error("MELCloud collector not available")
            return False
        
        logger.info(f"Collecting energy data for {target_date}")
        
        # Authenticate with MELCloud
        if not self.melcloud.authenticate():
            logger.error("MELCloud authentication failed")
            return False
        
        # Get devices
        if not self.melcloud.get_devices():
            logger.error("Failed to get MELCloud devices")
            return False
        
        # Get energy data for the date
        energy_data = self.melcloud.get_device_data_for_date(target_date)
        
        if energy_data:
            # Store data in database
            if self.melcloud.store_data_in_db(energy_data):
                logger.info(f"Successfully collected and stored energy data for {target_date}")
                return True
            else:
                logger.error(f"Failed to store energy data for {target_date}")
                return False
        else:
            logger.error(f"Failed to get energy data for {target_date}")
            return False
    
    def collect_temperature_data(self, target_date):
        """Collect temperature data for a specific date.
        
        Args:
            target_date: The date to collect data for
            
        Returns:
            True if successful, False otherwise
        """
        if not self.hass:
            logger.error("Home Assistant collector not available")
            return False
        
        logger.info(f"Collecting temperature data for {target_date}")
        
        # Fetch temperature data for the date
        temp, timestamp = self.hass.fetch_data_for_date(target_date)
        
        if temp is not None:
            logger.info(f"Successfully collected temperature data for {target_date}: {temp}°C")
            return True
        else:
            logger.error(f"Failed to collect temperature data for {target_date}")
            return False
    
    def ensure_monthly_prices(self):
        """Ensure that price data exists for the current month."""
        today = datetime.datetime.now()
        current_year = today.year
        current_month = today.month
        
        # Get the current price data
        price_data = self.db.get_prices_for_month(current_year, current_month)
        
        if not price_data:
            logger.info(f"No price data found for {current_year}-{current_month}. Adding default prices.")
            
            # Try to get the most recent price data
            previous_price = self.db.get_current_prices()
            
            if previous_price:
                # Use previous prices
                electricity_price = previous_price['electricity_price']
                diesel_price = previous_price['diesel_price']
                diesel_efficiency = previous_price['diesel_efficiency']
                logger.info(f"Using previous prices from {previous_price['year']}-{previous_price['month']}")
            else:
                # Default values for France
                electricity_price = 0.1946  # €/kWh (average price in France)
                diesel_price = 1.65  # €/liter (average price in France)
                diesel_efficiency = 0.85  # Typical efficiency for diesel heating
                logger.info("No previous prices found, using default values")
            
            # Add new price entry for current month
            self.db.update_prices(electricity_price, diesel_price, diesel_efficiency, 
                                current_year, current_month)
            logger.info(f"Added prices for {current_year}-{current_month}: " 
                        f"Electricity: {electricity_price} €/kWh, "
                        f"Diesel: {diesel_price} €/L, "
                        f"Efficiency: {diesel_efficiency}")
            return True
        else:
            logger.info(f"Price data already exists for {current_year}-{current_month}")
            return False
    
    def run_service(self, args=None):
        """Run the data collector service with the specified arguments."""
        if args is None:
            # Default arguments
            class Args:
                debug = False
                days_to_check = 180
                retry_hours = 2
                check_interval_hours = 24
            args = Args()
        
        logger.info("Starting data collector service")
        
        while True:
            try:
                # Check and ensure monthly prices exist
                self.ensure_monthly_prices()
                
                # Check for missing data
                missing_data = self.check_missing_data(days_to_check=args.days_to_check)
                
                if not missing_data:
                    logger.info(f"No missing data found in the last {args.days_to_check} days")
                else:
                    # Process missing dates, starting with the most recent
                    missing_dates = sorted(missing_data.keys(), reverse=True)
                    
                    logger.info(f"Attempting to collect data for {len(missing_dates)} dates with missing data")
                    
                    success_count = 0
                    
                    for date in missing_dates:
                        missing_types = missing_data[date]
                        logger.info(f"Processing {date} - Missing data: {', '.join(missing_types)}")
                        
                        success = True
                        
                        # Collect missing energy data
                        if "energy" in missing_types:
                            if self.collect_energy_data(date):
                                logger.info(f"Successfully collected energy data for {date}")
                            else:
                                logger.error(f"Failed to collect energy data for {date}")
                                success = False
                        
                        # Collect missing temperature data
                        if "temperature" in missing_types:
                            if self.collect_temperature_data(date):
                                logger.info(f"Successfully collected temperature data for {date}")
                            else:
                                logger.error(f"Failed to collect temperature data for {date}")
                                success = False
                        
                        if success:
                            success_count += 1
                    
                    logger.info(f"Collected data for {success_count} out of {len(missing_dates)} missing dates")
                
                # Calculate time until next check
                next_check = datetime.datetime.now() + datetime.timedelta(hours=args.check_interval_hours)
                logger.info(f"Next data check scheduled for {next_check}")
                
                # Wait until the next check
                time.sleep(args.check_interval_hours * 3600)
                
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received, exiting")
                break
            
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                import traceback
                logger.error(traceback.format_exc())
                
                # Wait before retrying
                retry_seconds = args.retry_hours * 3600
                logger.info(f"Retrying in {args.retry_hours} hours")
                time.sleep(retry_seconds)

def main():
    """Main function to run the service."""
    parser = argparse.ArgumentParser(description="Service to collect daily energy and temperature data.")
    parser.add_argument("--debug", help="Enable debug mode", action="store_true")
    parser.add_argument("--days-to-check", help="Number of days to check for missing data", type=int, default=180)
    parser.add_argument("--retry-hours", help="Hours to wait before retrying if collection fails", type=int, default=2)
    parser.add_argument("--check-interval-hours", help="Hours between data checks", type=int, default=24)
    args = parser.parse_args()
    
    # Create and run the service
    service = DataCollectorService(debug_mode=args.debug)
    service.run_service(args)

if __name__ == "__main__":
    main()