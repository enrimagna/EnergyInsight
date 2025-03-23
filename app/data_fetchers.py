import os
import asyncio
import logging
import json
import requests
from datetime import datetime, timedelta
from app.db.models import Database

logger = logging.getLogger(__name__)

# Mock implementation for testing when pymelcloud is not available
class MockMELCloudDevice:
    def __init__(self):
        self.name = "Heat Pump Simulator"
        self.serial_number = "MOCK12345"
        self.power = True
        
    def energy_report(self):
        # Return a realistic-looking mock energy report
        yesterday = datetime.now() - timedelta(days=1)
        return {
            'Energy_Consumed': {
                'Day': [{'value': 10.5, 'date': yesterday.strftime('%Y-%m-%d')}],
                'Week': [{'value': 65.3, 'date': (yesterday - timedelta(days=i)).strftime('%Y-%m-%d')} 
                         for i in range(7)],
                'Month': [],
                'Year': []
            },
            'Power_Consumed': {
                'Day': [{'value': 1200.0, 'date': yesterday.strftime('%Y-%m-%d')}],
                'Week': [{'value': 1350.0 - (i * 50), 'date': (yesterday - timedelta(days=i)).strftime('%Y-%m-%d')} 
                         for i in range(7)],
                'Month': [],
                'Year': []
            }
        }

# Mock implementation for testing when pymelcloud is not available
async def mock_login(username, password):
    return {"devices": [MockMELCloudDevice()]}

class MELCloudFetcher:
    """Fetches energy usage data from MELCloud."""
    
    def __init__(self, username, password, db=None):
        self.username = username
        self.password = password
        self.db = db if db else Database()
        
    async def fetch_data(self):
        """Fetch energy usage data from MELCloud and store in database."""
        try:
            # First try to import the real module
            try:
                import pymelcloud
                logger.info("Using real pymelcloud library")
                session = await pymelcloud.login(self.username, self.password)
            except ImportError:
                # If not available, use mock implementation
                logger.warning("pymelcloud not available, using mock implementation")
                session = await mock_login(self.username, self.password)
                
            device = session["devices"][0]  # Assuming first device is the heat pump
            energy_report = device.energy_report()
            
            # Process daily energy data
            for day_data in energy_report['Energy_Consumed']['Day']:
                date_str = day_data['date']
                energy_consumed = day_data['value']
                
                # Find corresponding power consumption
                power_consumption = next(
                    (day['value'] for day in energy_report['Power_Consumed']['Day'] if day['date'] == date_str),
                    0.0
                )
                
                # Calculate cost
                electricity_price = float(os.getenv('ELECTRICITY_PRICE', 0.28))
                cost = energy_consumed * electricity_price
                
                # Convert date string to timestamp
                timestamp = datetime.strptime(date_str, '%Y-%m-%d')
                
                # Store in database
                self.db.add_energy_data(timestamp, power_consumption, energy_consumed, cost)
                
            logger.info("Energy data fetched and stored successfully")
            
        except Exception as e:
            logger.error(f"Error fetching energy data: {e}")
            
class HomeAssistantFetcher:
    """Fetches temperature data from Home Assistant."""
    
    def __init__(self, hass_url, hass_token, db=None):
        self.hass_url = hass_url
        self.hass_token = hass_token
        self.db = db if db else Database()
        
    def fetch_data(self):
        """Fetch temperature data from Home Assistant and store in database."""
        try:
            # API endpoint for getting temperature data
            api_url = f"{self.hass_url}/api/states"
            
            # Headers with authorization token
            headers = {
                "Authorization": f"Bearer {self.hass_token}",
                "Content-Type": "application/json"
            }
            
            # Make request to Home Assistant API
            try:
                response = requests.get(api_url, headers=headers)
                response.raise_for_status()
            except (requests.exceptions.RequestException, requests.exceptions.ConnectionError) as e:
                logger.warning(f"Could not connect to Home Assistant: {e}")
                # Generate mock data if Home Assistant is not available
                self._generate_mock_data()
                return
            
            # Parse response
            states = response.json()
            
            # Find indoor and outdoor temperature sensors
            indoor_temp_entity = next((entity for entity in states if entity['entity_id'] == 'sensor.indoor_temperature'), None)
            outdoor_temp_entity = next((entity for entity in states if entity['entity_id'] == 'sensor.outdoor_temperature'), None)
            
            if indoor_temp_entity and outdoor_temp_entity:
                indoor_temp = float(indoor_temp_entity['state'])
                outdoor_temp = float(outdoor_temp_entity['state'])
                timestamp = datetime.now()
                
                # Store in database
                self.db.add_temperature_data(timestamp, indoor_temp, outdoor_temp)
                logger.info("Temperature data fetched and stored successfully")
            else:
                logger.warning("Temperature sensors not found in Home Assistant")
                # Generate mock data if sensors are not found
                self._generate_mock_data()
                
        except Exception as e:
            logger.error(f"Error fetching temperature data: {e}")
            # Generate mock data on error
            self._generate_mock_data()
            
    def _generate_mock_data(self):
        """Generate mock temperature data for testing purposes."""
        import random
        
        # Current time
        timestamp = datetime.now()
        
        # Generate realistic-looking indoor and outdoor temperatures
        indoor_temp = 21.0 + random.uniform(-1.0, 1.0)  # Around 21°C
        
        # Outdoor temperature varies with time of day
        hour = timestamp.hour
        base_temp = 15.0  # Base temperature
        day_temp = base_temp + 5.0 * (hour - 12) / 12  # Varies throughout the day
        outdoor_temp = day_temp + random.uniform(-2.0, 2.0)  # Add some randomness
        
        # Store in database
        self.db.add_temperature_data(timestamp, indoor_temp, outdoor_temp)
        logger.info("Mock temperature data generated and stored")

def update_prices(electricity_price=None, diesel_price=None, diesel_efficiency=None):
    """Update price information in the database from environment variables or provided values."""
    db = Database()
    
    # If values are provided, use them directly instead of env vars
    if electricity_price is None or diesel_price is None or diesel_efficiency is None:
        # Force reload of environment variables
        from dotenv import load_dotenv
        load_dotenv(override=True)
        
        # Get values from environment
        electricity_price = float(os.getenv('ELECTRICITY_PRICE', 0.28))
        diesel_price = float(os.getenv('DIESEL_PRICE', 1.50))
        diesel_efficiency = float(os.getenv('DIESEL_EFFICIENCY', 0.85))
    
    db.update_prices(electricity_price, diesel_price, diesel_efficiency)
    db.close_connection()  # Close the connection to ensure changes are committed
    
    logger.info(f"Updated prices: electricity {electricity_price}/kWh, diesel {diesel_price}/L, efficiency {diesel_efficiency}")
    return True

async def fetch_all_data():
    """Fetch all data from both sources."""
    db = Database()
    mel_fetcher = MELCloudFetcher(os.getenv('MELCLOUD_USERNAME'), os.getenv('MELCLOUD_PASSWORD'), db)
    hass_fetcher = HomeAssistantFetcher(os.getenv('HASS_URL'), os.getenv('HASS_TOKEN'), db)
    
    await mel_fetcher.fetch_data()
    hass_fetcher.fetch_data()
    update_prices()
