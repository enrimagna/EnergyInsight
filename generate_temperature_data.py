#!/usr/bin/env python3
import datetime
import random
import logging
from app.db.models import Database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def generate_temperature_data(days=30):
    """
    Generate realistic temperature data for the past X days
    """
    logger.info(f"Generating temperature data for the past {days} days")
    
    db = Database()
    
    # Generate data for each day
    end_date = datetime.datetime.now().date()
    start_date = end_date - datetime.timedelta(days=days)
    
    current_date = start_date
    while current_date <= end_date:
        # Generate realistic temperature values
        # Indoor temperature between 19-23°C
        indoor_temp = round(random.uniform(19.0, 23.0), 1)
        
        # Outdoor temperature varies by season
        month = current_date.month
        if 3 <= month <= 5:  # Spring
            outdoor_base = 15.0
            outdoor_variation = 8.0
        elif 6 <= month <= 8:  # Summer
            outdoor_base = 22.0
            outdoor_variation = 7.0
        elif 9 <= month <= 11:  # Fall
            outdoor_base = 12.0
            outdoor_variation = 10.0
        else:  # Winter
            outdoor_base = 2.0
            outdoor_variation = 8.0
        
        outdoor_temp = round(random.uniform(
            outdoor_base - outdoor_variation,
            outdoor_base + outdoor_variation
        ), 1)
        
        # Flow and return temperatures (optional)
        flow_temp = round(random.uniform(35.0, 45.0), 1)
        return_temp = round(flow_temp - random.uniform(5.0, 10.0), 1)
        
        # Add to database
        logger.info(f"Adding temperature data for {current_date}: indoor={indoor_temp}°C, outdoor={outdoor_temp}°C")
        db.add_temperature_data(
            timestamp=current_date,
            indoor_temp=indoor_temp,
            outdoor_temp=outdoor_temp,
            flow_temp=flow_temp,
            return_temp=return_temp
        )
        
        current_date += datetime.timedelta(days=1)
    
    logger.info("Temperature data generation complete")

if __name__ == "__main__":
    generate_temperature_data()
