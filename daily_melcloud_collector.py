import os
import json
import requests
import datetime
import logging
import argparse
from dotenv import load_dotenv
from app.db.models import Database
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("melcloud_collector.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MELCloudCollector:
    def __init__(self, target_device_id=None, target_device_name=None, debug_mode=False):
        """Initialize the MELCloud data collector.
        
        Args:
            target_device_id: Specific device ID to target (overrides env var)
            target_device_name: Name of device to search for
            debug_mode: Whether to save raw API responses
        """
        self.target_device_id = target_device_id if target_device_id else os.getenv("MELCLOUD_DEVICE_ID")
        self.target_device_name = target_device_name
        self.debug_mode = debug_mode
        
        # Will be set after device list is retrieved
        self.device_id = None
        self.device_name = None
        self.building_id = None
        
        # Set in authenticate()
        self.context_key = None
        
        # Initialize DB connection
        self.db = Database()
        
        # Load environment variables
        load_dotenv()
        
        # Get credentials from environment variables
        self.username = os.getenv('MELCLOUD_USERNAME')
        self.password = os.getenv('MELCLOUD_PASSWORD')
        
        if not self.username or not self.password:
            raise ValueError("MELCloud credentials not found. Please set MELCLOUD_USERNAME and MELCLOUD_PASSWORD in .env file")
        
        # Create debug directory if in debug mode
        if self.debug_mode:
            os.makedirs("melcloud_debug", exist_ok=True)
        
        # Ensure prices exist in the database
        self._ensure_prices_exist()

    def _ensure_prices_exist(self):
        """Ensure that price data exists in the database."""
        price_data = self.db.get_current_prices()
        
        if not price_data:
            logger.info("No price data found in database. Adding default prices.")
            # Default values for France
            electricity_price = 0.1946  # €/kWh (average price in France)
            diesel_price = 1.65  # €/liter (average price in France)
            diesel_efficiency = 0.85  # Typical efficiency for diesel heating
            
            self.db.update_prices(electricity_price, diesel_price, diesel_efficiency)
            logger.info(f"Added default prices: Electricity: {electricity_price} €/kWh, Diesel: {diesel_price} €/L, Efficiency: {diesel_efficiency}")

    def authenticate(self):
        """Authenticate with MELCloud API."""
        logger.info(f"Authenticating with MELCloud as {self.username}")
        
        # Try different app versions for authentication
        app_versions = ["1.23.4.0", "1.19.1.1", "1.25.0.0"]
        
        for app_version in app_versions:
            logger.info(f"Trying authentication with AppVersion: {app_version}")
            
            auth_url = "https://app.melcloud.com/Mitsubishi.Wifi.Client/Login/ClientLogin"
            auth_data = {
                "Email": self.username,
                "Password": self.password,
                "Language": 0,
                "AppVersion": app_version,
                "Persist": True,
                "CaptchaResponse": None
            }
            
            try:
                response = requests.post(auth_url, json=auth_data)
                
                if response.status_code != 200:
                    logger.warning(f"Authentication failed with status code: {response.status_code}")
                    continue
                
                auth_result = response.json()
                
                # Save auth response if in debug mode
                if self.debug_mode:
                    with open(f"melcloud_debug/auth_response_{app_version}.json", "w") as f:
                        json.dump(auth_result, f, indent=2)
                
                if "ErrorId" in auth_result and auth_result["ErrorId"] is not None:
                    logger.warning(f"Authentication error: {auth_result.get('ErrorMessage', 'Unknown error')}")
                    continue
                
                if "LoginData" not in auth_result or auth_result["LoginData"] is None:
                    logger.warning("Invalid authentication response - LoginData not found")
                    continue
                
                self.context_key = auth_result["LoginData"].get("ContextKey")
                if not self.context_key:
                    logger.warning("Context key not found in authentication response")
                    continue
                
                logger.info(f"Successfully authenticated with MELCloud using AppVersion {app_version}")
                return True
                
            except Exception as e:
                logger.error(f"Error during authentication: {str(e)}")
        
        logger.error("All authentication attempts failed")
        return False

    def get_devices(self):
        """Get list of devices from MELCloud API."""
        if not self.context_key:
            logger.error("Not authenticated. Call authenticate() first.")
            return False
        
        logger.info("Fetching devices from MELCloud")
        
        url = "https://app.melcloud.com/Mitsubishi.Wifi.Client/User/ListDevices"
        headers = {
            "X-MitsContextKey": self.context_key
        }
        
        try:
            response = requests.get(url, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch devices with status code: {response.status_code}")
                return False
            
            buildings = response.json()
            
            # Save raw devices response if in debug mode
            if self.debug_mode:
                with open("melcloud_debug/devices_response.json", "w") as f:
                    json.dump(buildings, f, indent=2)
                logger.info("Saved raw devices response to melcloud_debug/devices_response.json")
            
            if not buildings:
                logger.error("No buildings found in MELCloud account")
                return False
            
            logger.info(f"Found {len(buildings)} building(s)")
            
            # Look for the target device
            target_device_found = False
            
            for building in buildings:
                if "Structure" not in building or "Devices" not in building["Structure"]:
                    logger.warning(f"No devices found in building {building.get('Name', 'Unknown')}")
                    continue
                
                devices = building["Structure"]["Devices"]
                
                if not devices:
                    logger.warning(f"Empty devices list in building {building.get('Name', 'Unknown')}")
                    continue
                
                for device in devices:
                    device_id = device.get("DeviceID")
                    device_name = device.get("DeviceName")
                    
                    # If a specific device ID was requested, check for it
                    if self.target_device_id and str(device_id) == str(self.target_device_id):
                        self.device_id = device_id
                        self.device_name = device_name
                        self.building_id = building.get("ID")
                        target_device_found = True
                        logger.info(f"Found target device: {device_name} (ID: {device_id})")
                        break
                    
                    # If a specific device name was requested, check for it
                    elif self.target_device_name and self.target_device_name.lower() in device_name.lower():
                        self.device_id = device_id
                        self.device_name = device_name
                        self.building_id = building.get("ID")
                        target_device_found = True
                        logger.info(f"Found device by name: {device_name} (ID: {device_id})")
                        break
                
                if target_device_found:
                    break
            
            # If no specific device was requested or found, use the first device
            if not target_device_found and not self.device_id:
                for building in buildings:
                    if "Structure" not in building or "Devices" not in building["Structure"]:
                        continue
                    
                    devices = building["Structure"]["Devices"]
                    
                    if devices:
                        self.device_id = devices[0].get("DeviceID")
                        self.device_name = devices[0].get("DeviceName")
                        self.building_id = building.get("ID")
                        logger.info(f"No target device specified, using first available: {self.device_name} (ID: {self.device_id})")
                        target_device_found = True
                        break
            
            if not target_device_found:
                logger.error("No suitable device found in MELCloud account")
                return False
            
            logger.info(f"Using device: {self.device_name} (ID: {self.device_id}) in building ID: {self.building_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error fetching devices: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def get_energy_report_for_date_range(self, start_date, end_date):
        """Get energy report for a date range from MELCloud API."""
        if not self.context_key or not self.device_id:
            logger.error("Not properly initialized. Call authenticate() and get_devices() first.")
            return None
        
        # Add some padding to ensure we get all requested dates
        from_date = start_date - datetime.timedelta(days=3)
        to_date = end_date + datetime.timedelta(days=3)
        
        logger.info(f"Fetching energy report from MELCloud for date range: {from_date} to {to_date}")
        
        energy_url = f"https://app.melcloud.com/Mitsubishi.Wifi.Client/EnergyCost/Report"
        headers = {
            "X-MitsContextKey": self.context_key
        }
        payload = {
            "DeviceId": self.device_id,
            "UseCurrency": False,
            "FromDate": f"{from_date.strftime('%Y-%m-%d')}T00:00:00",
            "ToDate": f"{to_date.strftime('%Y-%m-%d')}T00:00:00"
        }
        
        try:
            response = requests.post(energy_url, headers=headers, json=payload)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch energy report with status code: {response.status_code}")
                return None
            
            energy_data = response.json()
            
            if not energy_data:
                logger.error("Empty energy report response")
                return None
            
            # Save energy report data if in debug mode
            if self.debug_mode:
                os.makedirs('melcloud_debug', exist_ok=True)
                debug_file = f"melcloud_debug/energy_report_{start_date}_to_{end_date}.json"
                with open(debug_file, "w") as f:
                    json.dump(energy_data, f, indent=2)
                logger.info(f"Saved energy report data to {debug_file}")
            
            return energy_data
            
        except Exception as e:
            logger.error(f"Error fetching energy report: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def process_energy_report_for_date(self, energy_data, target_date):
        """Extract energy data for a specific date from an energy report."""
        if not energy_data:
            logger.error("No energy data provided")
            return None
        
        # Extract basic device data from the current state
        device_data = self.get_current_device_data()
        if not device_data:
            logger.error("Failed to get current device data")
            return None
        
        room_temp = device_data.get("RoomTemperatureZone1", 0) or 0
        outdoor_temp = device_data.get("OutdoorTemperature", 0) or 0
        flow_temp = device_data.get("FlowTemperature", 0) or 0
        return_temp = device_data.get("ReturnTemperature", 0) or 0
        power = device_data.get("Power", False)
        operation_mode = device_data.get("OperationMode", 0)
        demand_percentage = device_data.get("DemandPercentage", 0) or 0
        
        # Default energy values
        heating_consumed = 0
        hot_water_consumed = 0
        heating_produced = 0
        hot_water_produced = 0
        
        # Convert date to string for comparison and extract day number
        date_str = target_date.strftime("%Y-%m-%d")
        target_day = target_date.day
        target_month = target_date.month
        target_year = target_date.year
        
        logger.info(f"Processing energy data for {date_str} (day {target_day})")
        
        # Get the reported date range from the energy report
        from_date_str = energy_data.get("FromDate", "")
        to_date_str = energy_data.get("ToDate", "")
        
        try:
            # Parse the dates from the report
            if from_date_str and "T" in from_date_str:
                from_date = datetime.datetime.strptime(from_date_str.split("T")[0], "%Y-%m-%d").date()
                logger.info(f"Energy report start date: {from_date}")
            else:
                logger.warning(f"Invalid FromDate in energy report: {from_date_str}")
                from_date = None
                
            if to_date_str and "T" in to_date_str:
                to_date = datetime.datetime.strptime(to_date_str.split("T")[0], "%Y-%m-%d").date()
                logger.info(f"Energy report end date: {to_date}")
            else:
                logger.warning(f"Invalid ToDate in energy report: {to_date_str}")
                to_date = None
        except Exception as e:
            logger.error(f"Error parsing dates from energy report: {e}")
            from_date = None
            to_date = None
        
        # Find the target date in the Labels array
        labels = energy_data.get("Labels", [])
        
        if not labels:
            logger.warning(f"No Labels array found in energy report for {date_str}")
            # Still return valid data with zeros for energy values
            return self._create_result_object(
                target_date, 0, 0, 0, 0, 0, 
                room_temp, outdoor_temp, flow_temp, return_temp,
                power, operation_mode, demand_percentage
            )
        
        logger.info(f"Labels in energy report: {labels}")
        
        target_index = None
        
        # Determine if labels are dates or day numbers
        is_date_format = False
        for label in labels:
            if isinstance(label, str) and "-" in label:
                is_date_format = True
                break
        
        # First check: direct match in Labels array
        if is_date_format:
            # Labels are date strings
            for i, label in enumerate(labels):
                if isinstance(label, str) and date_str in label:
                    target_index = i
                    logger.info(f"Found direct date match {date_str} at index {i}")
                    break
        else:
            # Labels may be day numbers (most common case)
            for i, label in enumerate(labels):
                if isinstance(label, (int, float)) and int(label) == target_day:
                    # Need to verify we're talking about the same month
                    if from_date and from_date.month == target_month and from_date.year == target_year:
                        target_index = i
                        logger.info(f"Found day {target_day} at index {i} with matching month/year")
                        break
                    elif i < len(labels) - 1 and labels[i+1] == target_day + 1:
                        # Sequential days, likely the right date
                        target_index = i
                        logger.info(f"Found sequential day {target_day} at index {i}")
                        break
        
        # Second check: calculate index based on date offset from from_date
        if target_index is None and from_date and to_date:
            if from_date <= target_date <= to_date:
                # Target date is in range of the report
                offset = (target_date - from_date).days
                if 0 <= offset < len(labels):
                    target_index = offset
                    logger.info(f"Calculated index {target_index} based on date offset from {from_date}")
                else:
                    logger.warning(f"Date offset {offset} out of range for labels array length {len(labels)}")
        
        # If we found an index into the arrays, extract the energy values
        if target_index is not None:
            logger.info(f"Retrieving energy data at index {target_index}")
            
            # Extract heating consumption
            if "Heating" in energy_data and target_index < len(energy_data["Heating"]):
                heating_item = energy_data["Heating"][target_index]
                if isinstance(heating_item, (int, float)):
                    heating_consumed = heating_item
                elif isinstance(heating_item, dict) and "Value" in heating_item:
                    heating_consumed = heating_item.get("Value", 0) or 0
                logger.info(f"Heating consumption: {heating_consumed} kWh")
            
            # Extract hot water consumption
            if "HotWater" in energy_data and target_index < len(energy_data["HotWater"]):
                hotwater_item = energy_data["HotWater"][target_index]
                if isinstance(hotwater_item, (int, float)):
                    hot_water_consumed = hotwater_item
                elif isinstance(hotwater_item, dict) and "Value" in hotwater_item:
                    hot_water_consumed = hotwater_item.get("Value", 0) or 0
                logger.info(f"Hot water consumption: {hot_water_consumed} kWh")
            
            # Extract heating production
            if "ProducedHeating" in energy_data and target_index < len(energy_data["ProducedHeating"]):
                prod_heating = energy_data["ProducedHeating"][target_index]
                if isinstance(prod_heating, (int, float)):
                    heating_produced = prod_heating
                elif isinstance(prod_heating, dict) and "Value" in prod_heating:
                    heating_produced = prod_heating.get("Value", 0) or 0
                logger.info(f"Heating production: {heating_produced} kWh")
            
            # Extract hot water production
            if "ProducedHotWater" in energy_data and target_index < len(energy_data["ProducedHotWater"]):
                prod_hotwater = energy_data["ProducedHotWater"][target_index]
                if isinstance(prod_hotwater, (int, float)):
                    hot_water_produced = prod_hotwater
                elif isinstance(prod_hotwater, dict) and "Value" in prod_hotwater:
                    hot_water_produced = prod_hotwater.get("Value", 0) or 0
                logger.info(f"Hot water production: {hot_water_produced} kWh")
            
            # Extract COP directly if available
            cop_from_report = None
            if "CoP" in energy_data and target_index < len(energy_data["CoP"]):
                cop_item = energy_data["CoP"][target_index]
                if isinstance(cop_item, (int, float)):
                    cop_from_report = cop_item
                    logger.info(f"COP from report: {cop_from_report}")
        else:
            # If date not found in report, log a message and return zeros
            if from_date and to_date:
                date_range_msg = f"The report only contains data from {from_date} to {to_date}"
            else:
                date_range_msg = "Could not determine the date range in the report"
                
            logger.warning(f"Date {date_str} not found in energy report. {date_range_msg}")
            logger.warning(f"Available data in Labels: {labels}")
            logger.warning(f"Returning zero values for energy metrics for {date_str}")
            
            # Return valid data with zeros for energy values
            return self._create_result_object(
                target_date, 0, 0, 0, 0, 0, 
                room_temp, outdoor_temp, flow_temp, return_temp,
                power, operation_mode, demand_percentage
            )
        
        # Calculate totals
        total_consumed = heating_consumed + hot_water_consumed
        total_produced = heating_produced + hot_water_produced
        
        # Use COP from report if available, otherwise calculate it
        if cop_from_report is not None:
            cop = cop_from_report
        else:
            cop = total_produced / total_consumed if total_consumed > 0 else 0
        
        # Create result object
        return self._create_result_object(
            target_date, heating_consumed, hot_water_consumed, heating_produced, hot_water_produced, cop,
            room_temp, outdoor_temp, flow_temp, return_temp, power, operation_mode, demand_percentage
        )

    def _create_result_object(self, date, heating_consumed, hot_water_consumed, heating_produced, hot_water_produced, cop,
                             room_temp, outdoor_temp, flow_temp, return_temp, power, operation_mode, demand_percentage):
        """Create a standardized result object with all required fields."""
        # Map operation mode to text
        operation_modes = {
            0: "Heat",
            1: "Dry",
            2: "Cool",
            3: "Vent",
            4: "Auto",
            5: "Unknown"
        }
        operation_mode_text = operation_modes.get(operation_mode, f"Unknown ({operation_mode})")
        
        # Calculate totals
        total_consumed = heating_consumed + hot_water_consumed
        total_produced = heating_produced + hot_water_produced
        
        # Get electricity price
        price_data = self.db.get_current_prices()
        electricity_price = price_data['electricity_price'] if price_data else 0.1946
        
        # Calculate cost
        cost = total_consumed * electricity_price
        
        # Create result object
        result = {
            "date": date,
            "heating_consumed": heating_consumed,
            "hot_water_consumed": hot_water_consumed,
            "total_consumed": total_consumed,
            "heating_produced": heating_produced,
            "hot_water_produced": hot_water_produced,
            "total_produced": total_produced,
            "cop": cop,
            "room_temp": room_temp,
            "outdoor_temp": outdoor_temp,
            "flow_temp": flow_temp,
            "return_temp": return_temp,
            "power": power,
            "operation_mode": operation_mode_text,
            "demand_percentage": demand_percentage,
            "cost": cost
        }
        
        # Print summary
        print(f"\nEnergy data for {date.strftime('%Y-%m-%d')}:")
        print(f"  Heating consumption: {heating_consumed:.2f} kWh")
        print(f"  Hot water consumption: {hot_water_consumed:.2f} kWh")
        print(f"  Heating production: {heating_produced:.2f} kWh")
        print(f"  Hot water production: {hot_water_produced:.2f} kWh")
        print(f"  COP: {cop:.2f}")
        print(f"  Cost: {cost:.2f} €")
        
        return result

    def get_current_device_data(self):
        """Get current device data from MELCloud API."""
        if not self.context_key or not self.device_id or not self.building_id:
            logger.error("Not properly initialized. Call authenticate() and get_devices() first.")
            return None
        
        device_url = f"https://app.melcloud.com/Mitsubishi.Wifi.Client/Device/Get"
        headers = {
            "X-MitsContextKey": self.context_key
        }
        params = {
            "id": self.device_id,
            "buildingID": self.building_id
        }
        
        try:
            response = requests.get(device_url, headers=headers, params=params)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch current device data with status code: {response.status_code}")
                return None
            
            device_data = response.json()
            
            if not device_data:
                logger.error("Empty device data response")
                return None
            
            return device_data
            
        except Exception as e:
            logger.error(f"Error fetching current device data: {str(e)}")
            return None

    def get_device_data_for_date(self, target_date):
        """Get device data for a specific date from MELCloud API."""
        if not self.context_key or not self.device_id or not self.building_id:
            logger.error("Not properly initialized. Call authenticate() and get_devices() first.")
            return None
        
        logger.info(f"Fetching device data from MELCloud for date: {target_date}")
        
        # Get energy report for the date range
        energy_data = self.get_energy_report_for_date_range(target_date, target_date)
        
        if energy_data:
            # Process the energy report for the target date
            return self.process_energy_report_for_date(energy_data, target_date)
        else:
            logger.error(f"Failed to get energy report for {target_date}")
            return None

    def get_device_data_for_date_range(self, start_date, end_date):
        """Get device data for a range of dates from MELCloud API."""
        if not self.context_key or not self.device_id or not self.building_id:
            logger.error("Not properly initialized. Call authenticate() and get_devices() first.")
            return None
        
        logger.info(f"Fetching device data from MELCloud for date range: {start_date} to {end_date}")
        
        # Get energy report for the date range
        energy_data = self.get_energy_report_for_date_range(start_date, end_date)
        
        if energy_data:
            # Process the energy report for each date in the range
            results = []
            current_date = start_date
            
            while current_date <= end_date:
                result = self.process_energy_report_for_date(energy_data, current_date)
                if result:
                    results.append(result)
                current_date += datetime.timedelta(days=1)
            
            return results
        else:
            logger.error(f"Failed to get energy report for date range: {start_date} to {end_date}")
            return None

    def store_data_in_db(self, data):
        """Store data in the database."""
        if not data:
            logger.error("No data to store in database")
            return False
        
        try:
            # Add energy data to database
            result = self.db.add_melcloud_data(
                date=data["date"],
                heating_consumed=data["heating_consumed"],
                hot_water_consumed=data["hot_water_consumed"],
                heating_produced=data["heating_produced"],
                hot_water_produced=data["hot_water_produced"],
                cop=data["cop"],
                power_consumption=data["demand_percentage"],
                cost=data["cost"],
                device_id=self.device_id,
                device_name=self.device_name,
                operation_mode=data["operation_mode"],
                demand_percentage=data["demand_percentage"]
            )
            
            if result:
                logger.info(f"Successfully stored energy data for {data['date']}")
            else:
                logger.warning(f"Failed to store energy data for {data['date']}")
            
            # Add temperature data to database
            temp_result = self.db.add_temperature_data(
                timestamp=data["date"],
                indoor_temp=data["room_temp"],
                outdoor_temp=data["outdoor_temp"],
                flow_temp=data["flow_temp"],
                return_temp=data["return_temp"]
            )
            
            if temp_result:
                logger.info(f"Successfully stored temperature data for {data['date']}")
            else:
                logger.warning(f"Failed to store temperature data for {data['date']}")
            
            return result and temp_result
            
        except Exception as e:
            logger.error(f"Error storing data in database: {str(e)}")
            return False

    def collect_daily_data(self):
        """Collect today's data from MELCloud and store it in the database."""
        logger.info("Starting daily MELCloud data collection")
        
        # Authenticate with MELCloud
        if not self.authenticate():
            logger.error("Authentication failed. Aborting.")
            return False
        
        # Get devices
        if not self.get_devices():
            logger.error("Failed to get devices. Aborting.")
            return False
        
        # Get current device data
        data = self.get_device_data_for_date(datetime.date.today())
        
        if data:
            # Store data in database
            if self.store_data_in_db(data):
                logger.info(f"Successfully collected and stored MELCloud data for {data['date']}")
                return True
            else:
                logger.error(f"Failed to store MELCloud data for {data['date']}")
                return False
        else:
            logger.error("Failed to get device data from MELCloud")
            return False

    def collect_data_for_date_range(self, start_date, end_date):
        """Collect data for a range of dates from MELCloud and store it in the database."""
        logger.info(f"Starting MELCloud data collection for date range: {start_date} to {end_date}")
        
        # Convert string dates to datetime objects if necessary
        if isinstance(start_date, str):
            try:
                start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
            except ValueError:
                logger.error(f"Invalid start date format: {start_date}. Expected YYYY-MM-DD")
                return False
                
        if isinstance(end_date, str):
            try:
                end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
            except ValueError:
                logger.error(f"Invalid end date format: {end_date}. Expected YYYY-MM-DD")
                return False
        
        # Ensure end_date is not before start_date
        if end_date < start_date:
            logger.error(f"End date {end_date} is before start date {start_date}")
            return False
        
        # Authenticate with MELCloud
        if not self.authenticate():
            logger.error("Authentication failed. Aborting.")
            return False
        
        # Get devices
        if not self.get_devices():
            logger.error("Failed to retrieve devices. Aborting.")
            return False
        
        # Get device data for the date range
        data_list = self.get_device_data_for_date_range(start_date, end_date)
        
        if data_list:
            # Store data in database
            success_count = 0
            for data in data_list:
                if self.store_data_in_db(data):
                    logger.info(f"Successfully stored MELCloud data for {data['date']}")
                    success_count += 1
                else:
                    logger.error(f"Failed to store MELCloud data for {data['date']}")
            
            logger.info(f"Data collection complete. Successfully processed {success_count} out of {(end_date - start_date).days + 1} days")
            return success_count > 0
        else:
            logger.error(f"Failed to get device data for date range: {start_date} to {end_date}")
            return False

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Collect daily energy data from MELCloud.")
    parser.add_argument("--start-date", help="Start date for the collection (format: YYYY-MM-DD)", default=None)
    parser.add_argument("--end-date", help="End date for the collection (format: YYYY-MM-DD)", default=None)
    parser.add_argument("--device-id", help="Specific device ID to process", default=os.getenv("MELCLOUD_DEVICE_ID"))
    parser.add_argument("--device-name", help="Device name to search for", default=None)
    parser.add_argument("--debug", help="Enable debug mode", action="store_true")
    parser.add_argument("--raw-only", help="Only download raw data, don't insert into the database", action="store_true")
    parser.add_argument("--batch-size", help="Number of days to process in each API request", type=int, default=30)
    args = parser.parse_args()

    # Create debug directory if it doesn't exist
    if args.debug and not os.path.exists("melcloud_debug"):
        os.makedirs("melcloud_debug")

    # Set up the collector
    collector = MELCloudCollector(target_device_id=args.device_id, target_device_name=args.device_name, debug_mode=args.debug)

    # Process dates
    if args.start_date:
        start_date = datetime.datetime.strptime(args.start_date, "%Y-%m-%d").date()
        
        if args.end_date:
            end_date = datetime.datetime.strptime(args.end_date, "%Y-%m-%d").date()
        else:
            end_date = start_date
    else:
        # Default to yesterday if no date is provided
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        start_date = yesterday
        end_date = yesterday

    # Calculate total days to process
    total_days = (end_date - start_date).days + 1

    # Print configuration
    print("\n=== MELCloud Daily Collector ===")
    print(f"Processing date range: {start_date} to {end_date} ({total_days} days)")
    print(f"Device ID: {collector.device_id}")
    print(f"Debug mode: {'Enabled' if args.debug else 'Disabled'}")
    print(f"Raw only mode: {'Enabled' if args.raw_only else 'Disabled'}")
    print(f"Batch size: {args.batch_size} days")
    print("================================\n")
    
    # Initialize authentication
    if not collector.authenticate():
        print("Authentication failed. Please check your credentials.")
        return False
    
    # Get devices to initialize building ID, etc.
    if not collector.get_devices():
        print("Failed to retrieve devices. Please check your connection.")
        return False
    
    # Process the date range in smaller batches
    # MELCloud tends to return limited chunks of data regardless of requested range
    # So we'll use a smaller batch size to improve our chances of getting data
    actual_batch_size = min(args.batch_size, 14)  # Max 14 days per request for better reliability
    
    current_start = start_date
    successful_days = 0
    failed_days = 0
    
    print(f"\nProcessing {total_days} days in batches of {actual_batch_size}...\n")
    
    while current_start <= end_date:
        # Calculate the end of the current batch
        current_end = min(current_start + datetime.timedelta(days=actual_batch_size - 1), end_date)
        days_in_batch = (current_end - current_start).days + 1
        
        print(f"\nBatch: {current_start} to {current_end} ({days_in_batch} days)")
        print(f"Progress: {(current_start - start_date).days}/{total_days} days processed ({(current_start - start_date).days/total_days*100:.1f}% complete)")
        
        # Get energy data for the batch 
        energy_data = collector.get_energy_report_for_date_range(current_start, current_end)
        
        if not energy_data:
            print(f"Failed to retrieve energy data for {current_start} to {current_end}")
            failed_days += days_in_batch
            current_start = current_end + datetime.timedelta(days=1)
            continue
        
        # Get the actual date range returned in the report
        actual_from = None
        actual_to = None
        
        try:
            from_date_str = energy_data.get("FromDate", "")
            to_date_str = energy_data.get("ToDate", "")
            
            if from_date_str and "T" in from_date_str:
                actual_from = datetime.datetime.strptime(from_date_str.split("T")[0], "%Y-%m-%d").date()
            
            if to_date_str and "T" in to_date_str:
                actual_to = datetime.datetime.strptime(to_date_str.split("T")[0], "%Y-%m-%d").date()
            
            if actual_from and actual_to:
                print(f"Note: MELCloud returned data for {actual_from} to {actual_to} (requested: {current_start} to {current_end})")
                
                # If the returned range is completely different, adjust our expectations
                if actual_from > current_end or actual_to < current_start:
                    print(f"Warning: Returned date range does not overlap with requested range!")
        except Exception as e:
            print(f"Error parsing returned date range: {e}")
        
        # Process each day in the batch
        batch_date = current_start
        while batch_date <= current_end:
            print(f"\nProcessing date: {batch_date} ({(batch_date - start_date).days + 1}/{total_days})")
            
            # Process the energy data for this date
            result = collector.process_energy_report_for_date(energy_data, batch_date)
            
            if result:
                has_energy_data = (result['heating_consumed'] > 0 or 
                                  result['hot_water_consumed'] > 0 or 
                                  result['heating_produced'] > 0 or 
                                  result['hot_water_produced'] > 0)
                
                # If we got a result but all energy values are zero, we might not have actual data
                if not has_energy_data:
                    print(f"⚠ No energy data found for {batch_date} (returning zeros)")
                
                # Store in database if not in raw-only mode
                if not args.raw_only:
                    if collector.store_data_in_db(result):
                        status = "✓" if has_energy_data else "⚠"
                        print(f"{status} Stored data for {batch_date}")
                        successful_days += 1
                    else:
                        print(f"✗ Failed to store data for {batch_date}")
                        failed_days += 1
                else:
                    status = "✓" if has_energy_data else "⚠"
                    print(f"{status} Processed data for {batch_date} (raw only)")
                    successful_days += 1
            else:
                print(f"✗ Failed to process data for {batch_date}")
                failed_days += 1
            
            batch_date += datetime.timedelta(days=1)
        
        # Move to the next batch
        current_start = current_end + datetime.timedelta(days=1)
    
    # Print summary
    print(f"\n=== Collection Summary ===")
    print(f"Total days: {total_days}")
    print(f"Successful days: {successful_days}")
    print(f"Failed days: {failed_days}")
    if total_days > 0:
        print(f"Success rate: {successful_days/total_days*100:.1f}%")
    print("=========================")
    
    if successful_days > 0:
        return True
    else:
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
