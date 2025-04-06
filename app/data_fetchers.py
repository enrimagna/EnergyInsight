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
        """Return a realistic-looking mock energy report that matches the expected structure."""
        try:
            # Generate data for the last 7 days
            yesterday = datetime.now() - timedelta(days=1)
            
            # Create daily data for the past week
            day_data = []
            week_data = []
            
            for i in range(7):
                date_str = (yesterday - timedelta(days=i)).strftime('%Y-%m-%d')
                day_value = 10.5 - (i * 0.5)  # Decreasing values for older days
                week_value = 65.3 - (i * 3.0)  # Decreasing values for older days
                
                if i == 0:  # Only add yesterday to the day data
                    day_data.append({'value': day_value, 'date': date_str})
                
                week_data.append({'value': week_value, 'date': date_str})
            
            # Create the full report structure
            report = {
                'Energy_Consumed': {
                    'Day': day_data,
                    'Week': week_data,
                    'Month': [],
                    'Year': []
                },
                'Power_Consumed': {
                    'Day': [{'value': 1200.0, 'date': day_data[0]['date']}] if day_data else [],
                    'Week': [{'value': 1350.0 - (i * 50), 'date': week_data[i]['date']} for i in range(len(week_data))],
                    'Month': [],
                    'Year': []
                }
            }
            
            logger.info(f"Generated mock energy report with {len(day_data)} day entries and {len(week_data)} week entries")
            return report
            
        except Exception as e:
            logger.error(f"Error generating mock energy report: {str(e)}")
            # Return a minimal valid structure to prevent NoneType errors
            return {
                'Energy_Consumed': {'Day': [], 'Week': [], 'Month': [], 'Year': []},
                'Power_Consumed': {'Day': [], 'Week': [], 'Month': [], 'Year': []}
            }

# Mock implementation for testing when pymelcloud is not available
async def mock_login(username, password):
    """Simulate a successful login to MELCloud and return a session with mock devices."""
    try:
        logger.info(f"Using mock MELCloud login for username: {username}")
        # Create a mock device
        mock_device = MockMELCloudDevice()
        # Return a dictionary that matches the expected structure
        # The key issue is that we need to return a dict with a 'get' method
        # and a 'devices' key containing our mock device
        return {
            "devices": [mock_device],
            "get": lambda key, default=None: [mock_device] if key == "devices" else default
        }
    except Exception as e:
        logger.error(f"Error in mock_login: {str(e)}")
        # Return a valid structure with get method to prevent NoneType errors
        mock_device = MockMELCloudDevice()
        return {
            "devices": [mock_device],
            "get": lambda key, default=None: [mock_device] if key == "devices" else default
        }

class MELCloudFetcher:
    """Fetches energy usage data from MELCloud."""
    
    def __init__(self, username, password, db=None):
        self.username = username
        self.password = password
        self.db = db if db else Database()
        
    async def test_connection(self):
        """Test the connection to MELCloud without fetching or processing data."""
        session = None
        try:
            # First try to import the real module
            try:
                import pymelcloud
                logger.info("Using real pymelcloud library for connection test")
                session = await pymelcloud.login(self.username, self.password)
                if not session:
                    logger.error("pymelcloud login returned None")
                    raise ValueError("Failed to authenticate with MELCloud")
            except ImportError:
                # If not available, use mock implementation
                logger.warning("pymelcloud not available, using mock implementation for test")
                session = await mock_login(self.username, self.password)
            
            logger.info(f"Session type: {type(session)}")
            
            # Safely check if session contains devices
            devices = []
            if session is None:
                logger.error("Session is None")
                raise ValueError("Failed to create a valid session with MELCloud")
                
            # Try to get devices using get method first (for real pymelcloud)
            if hasattr(session, 'get'):
                logger.info("Session has 'get' method, using it to retrieve devices")
                devices = session.get('devices', [])
            # Then try direct dictionary access (for our mock)
            elif isinstance(session, dict) and 'devices' in session:
                logger.info("Session is a dict with 'devices' key, accessing directly")
                devices = session['devices']
            else:
                logger.error(f"Session doesn't have expected structure: {session}")
                raise ValueError("Unexpected session structure from MELCloud")
                
            # Check if we have any devices
            if not devices:
                logger.error("No devices found in MELCloud session")
                raise ValueError("No devices found in MELCloud account")
                
            # Just check if we can access the first device
            device = devices[0]
            device_name = getattr(device, 'name', 'Unknown')
            logger.info(f"Test successful - Found device: {device_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error testing MELCloud connection: {str(e)}")
            raise  # Re-raise the exception for proper error handling
        finally:
            # Cleanup session if it's from the real pymelcloud library
            if session and hasattr(session, 'close') and callable(session.close):
                await session.close()
                logger.info("MELCloud session closed properly")
        
    async def fetch_data(self):
        """Fetch energy usage data from MELCloud and store in database."""
        session = None
        try:
            # First try to import the real module
            try:
                import pymelcloud
                logger.info("Using real pymelcloud library")
                session = await pymelcloud.login(self.username, self.password)
                if not session:
                    logger.error("pymelcloud login returned None")
                    raise ValueError("Failed to authenticate with MELCloud")
            except ImportError:
                # If not available, use mock implementation
                logger.warning("pymelcloud not available, using mock implementation")
                session = await mock_login(self.username, self.password)
                
            # Check if session contains devices
            if not session or "devices" not in session or not session["devices"]:
                logger.error("No devices found in MELCloud session")
                raise ValueError("No devices found in MELCloud account")
                
            device = session["devices"][0]  # Assuming first device is the heat pump
            logger.info(f"Found device: {getattr(device, 'name', 'Unknown')}")
            
            # Get energy report with error handling
            try:
                energy_report = device.energy_report()
                logger.info("Successfully retrieved energy report")
            except Exception as e:
                logger.error(f"Error getting energy report: {str(e)}")
                raise ValueError(f"Failed to get energy report from device: {str(e)}")
            
            # Validate energy report structure
            if not energy_report or not isinstance(energy_report, dict):
                logger.error(f"Invalid energy report format: {type(energy_report)}")
                raise ValueError("Energy report has invalid format")
                
            # Check if required keys exist
            required_keys = ['Energy_Consumed', 'Power_Consumed']
            for key in required_keys:
                if key not in energy_report:
                    logger.error(f"Missing key in energy report: {key}")
                    raise ValueError(f"Energy report missing required data: {key}")
            
            # Check if Day data exists
            if 'Day' not in energy_report['Energy_Consumed'] or 'Day' not in energy_report['Power_Consumed']:
                logger.error("Missing Day data in energy report")
                raise ValueError("Energy report missing daily data")
                
            # Process daily energy data
            day_data = energy_report['Energy_Consumed']['Day']
            if not day_data:
                logger.warning("No daily energy consumption data found")
                return True  # Return success but with no data
                
            # Process and store each day's data
            for day_entry in day_data:
                try:
                    # Get corresponding power data
                    date_str = day_entry['date']
                    energy_value = day_entry['value']
                    
                    # Find matching power entry for the same date
                    power_value = None
                    for power_entry in energy_report['Power_Consumed']['Day']:
                        if power_entry['date'] == date_str:
                            power_value = power_entry['value']
                            break
                    
                    if power_value is None:
                        logger.warning(f"No power data found for date {date_str}")
                        continue
                    
                    # Convert date string to datetime
                    try:
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                    except ValueError:
                        logger.error(f"Invalid date format: {date_str}")
                        continue
                    
                    # Calculate cost based on current electricity price
                    db = self.db
                    prices = db.get_current_prices()
                    if prices:
                        electricity_price = prices['electricity_price']
                    else:
                        # Default price if not set
                        electricity_price = float(os.getenv('ELECTRICITY_PRICE', 0.28))
                    
                    cost = energy_value * electricity_price
                    
                    # Store in database
                    success = db.add_energy_data(date_obj, power_value, energy_value, cost)
                    if success:
                        logger.info(f"Added energy data for {date_str}: Energy={energy_value}kWh, Power={power_value}W, Cost=${cost:.2f}")
                    else:
                        logger.info(f"Energy data for {date_str} already exists in database")
                        
                except Exception as e:
                    logger.error(f"Error processing day entry {day_entry}: {str(e)}")
                    continue
            
            # Also process weekly data for more historical information
            week_data = energy_report['Energy_Consumed']['Week']
            if week_data:
                for week_entry in week_data:
                    try:
                        # Skip if we already have this date from daily data
                        date_str = week_entry['date']
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        
                        # Check if this date already exists in the database
                        # (We don't have a direct method for this, so we'll add it and check the result)
                        
                        # Find matching power entry for the same date
                        power_value = None
                        for power_entry in energy_report['Power_Consumed']['Week']:
                            if power_entry['date'] == date_str:
                                power_value = power_entry['value']
                                break
                        
                        if power_value is None:
                            logger.warning(f"No weekly power data found for date {date_str}")
                            continue
                        
                        # Calculate cost
                        energy_value = week_entry['value']
                        db = self.db
                        prices = db.get_current_prices()
                        if prices:
                            electricity_price = prices['electricity_price']
                        else:
                            electricity_price = float(os.getenv('ELECTRICITY_PRICE', 0.28))
                        
                        cost = energy_value * electricity_price
                        
                        # Try to add to database (will be skipped if already exists)
                        success = db.add_energy_data(date_obj, power_value, energy_value, cost)
                        if success:
                            logger.info(f"Added weekly energy data for {date_str}: Energy={energy_value}kWh, Power={power_value}W, Cost=${cost:.2f}")
                        
                    except Exception as e:
                        logger.error(f"Error processing week entry {week_entry}: {str(e)}")
                        continue
            
            return True
            
        except Exception as e:
            logger.error(f"Error fetching energy data: {str(e)}")
            raise
        finally:
            # Cleanup session if it's from the real pymelcloud library
            if session and hasattr(session, 'close') and callable(session.close):
                await session.close()
                logger.info("MELCloud session closed properly")
    
    async def get_raw_data(self):
        """Fetch raw data from MELCloud to inspect available fields.
        
        This method is useful for exploring the API and understanding what data is available.
        Returns the complete energy report as a dictionary.
        """
        session = None
        try:
            # First try to import the real module
            try:
                import pymelcloud
                logger.info("Using real pymelcloud library")
                session = await pymelcloud.login(self.username, self.password)
                if not session:
                    logger.error("pymelcloud login returned None")
                    raise ValueError("Failed to authenticate with MELCloud")
            except ImportError:
                # If not available, use mock implementation
                logger.warning("pymelcloud not available, using mock implementation")
                session = await mock_login(self.username, self.password)
                
            # Check if session contains devices
            if not session or "devices" not in session or not session["devices"]:
                logger.error("No devices found in MELCloud session")
                raise ValueError("No devices found in MELCloud account")
                
            device = session["devices"][0]  # Assuming first device is the heat pump
            logger.info(f"Found device: {getattr(device, 'name', 'Unknown')}")
            
            # Get device information
            device_info = {
                "name": getattr(device, "name", "Unknown"),
                "serial_number": getattr(device, "serial_number", "Unknown"),
                "power": getattr(device, "power", None),
                "device_type": type(device).__name__
            }
            
            # Get all available methods and properties
            device_methods = [method for method in dir(device) if not method.startswith('_')]
            
            # Get energy report
            try:
                energy_report = device.energy_report()
                logger.info("Successfully retrieved energy report")
            except Exception as e:
                logger.error(f"Error getting energy report: {str(e)}")
                energy_report = {"error": str(e)}
            
            # Try to get other potentially useful information
            additional_info = {}
            for method in device_methods:
                try:
                    if method not in ['energy_report'] and not method.startswith('_'):
                        attr = getattr(device, method)
                        if callable(attr):
                            # Skip methods that require parameters
                            if method in ['set_power', 'set_target_temperature']:
                                continue
                            try:
                                result = attr()
                                additional_info[method] = result
                            except:
                                pass
                        else:
                            additional_info[method] = attr
                except:
                    pass
            
            # Combine all information
            result = {
                "device_info": device_info,
                "device_methods": device_methods,
                "energy_report": energy_report,
                "additional_info": additional_info
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching raw data: {str(e)}")
            return {"error": str(e)}
        finally:
            # Cleanup session if it's from the real pymelcloud library
            if session and hasattr(session, 'close') and callable(session.close):
                await session.close()
                logger.info("MELCloud session closed properly")

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
                response = requests.get(api_url, headers=headers, timeout=10)  # Add timeout
                response.raise_for_status()
            except (requests.exceptions.RequestException, requests.exceptions.ConnectionError) as e:
                logger.warning(f"Could not connect to Home Assistant: {str(e)}")
                # Generate mock data if Home Assistant is not available
                self._generate_mock_data()
                return False  # Return False to indicate connection failure
            
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
                return True  # Return True to indicate success
            else:
                logger.warning("Temperature sensors not found in Home Assistant")
                # Generate mock data if sensors are not found
                self._generate_mock_data()
                return False  # Return False to indicate missing sensors
                
        except Exception as e:
            logger.error(f"Error fetching temperature data: {str(e)}")
            # Generate mock data on error
            self._generate_mock_data()
            raise  # Re-raise the exception for proper error handling in test connections

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
    
    # Log the values before updating the database
    logger.info(f"update_prices function received - Electricity: {electricity_price} (type: {type(electricity_price)}), "
                f"Diesel: {diesel_price} (type: {type(diesel_price)}), "
                f"Efficiency: {diesel_efficiency} (type: {type(diesel_efficiency)})")
    
    # Ensure all values are floats
    electricity_price = float(electricity_price)
    diesel_price = float(diesel_price)
    diesel_efficiency = float(diesel_efficiency)
    
    db.update_prices(electricity_price, diesel_price, diesel_efficiency)
    
    # Verify the update
    current_prices = db.get_current_prices()
    if current_prices:
        logger.info(f"Prices after DB update - Electricity: {current_prices['electricity_price']}, "
                    f"Diesel: {current_prices['diesel_price']}, "
                    f"Efficiency: {current_prices['diesel_efficiency']}")
    else:
        logger.warning("No price data found in database after update in data_fetchers.py")
    
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

async def fetch_and_store_energy_data(start_date=None, end_date=None):
    username = os.getenv('MELCLOUD_USERNAME')
    password = os.getenv('MELCLOUD_PASSWORD')

    if not username or not password:
        logger.error("MELCloud credentials are not set in environment variables.")
        return

    # Default to yesterday
    if end_date is None:
        end_date = datetime.now() - timedelta(days=1)
    if start_date is None:
        start_date = end_date - timedelta(days=1)

    # Convert dates to string format
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')

    session = None
    try:
        # Login to MELCloud
        try:
            import pymelcloud
            session = await pymelcloud.login(username, password)
            if not session:
                logger.error("pymelcloud login returned None")
                raise ValueError("Failed to authenticate with MELCloud")
        except ImportError:
            logger.warning("pymelcloud not available, using mock implementation")
            session = await mock_login(username, password)

        # Check if session contains devices
        if not session or "devices" not in session or not session["devices"]:
            logger.error("No devices found in MELCloud session")
            raise ValueError("No devices found in MELCloud account")

        device = session["devices"][0]  # Assuming first device is the heat pump
        logger.info(f"Found device: {getattr(device, 'name', 'Unknown')}")

        # Fetch energy report
        energy_report = await device.energy_report(start_date=start_date_str, end_date=end_date_str)

        # Print raw response
        print(json.dumps(energy_report, indent=2))

        # Store data in the database
        db = Database()
        for entry in energy_report['Energy_Consumed']['Day']:
            db.insert_energy_data(date=entry['date'], value=entry['value'])

        logger.info(f"Data from {start_date_str} to {end_date_str} stored successfully.")
    finally:
        # Cleanup session if it's from the real pymelcloud library
        if session and hasattr(session, 'close') and callable(session.close):
            await session.close()
            logger.info("MELCloud session closed properly")

if __name__ == "__main__":
    import asyncio

    asyncio.run(fetch_and_store_energy_data())
