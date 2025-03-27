#!/usr/bin/env python3
"""
Simple script to extract and display energy data from MELCloud
"""
import os
import sys
import json
import datetime
import argparse
from dotenv import load_dotenv
import requests

def main():
    """Main function to extract and display energy data"""
    parser = argparse.ArgumentParser(description="Display MELCloud energy data for a specific date")
    parser.add_argument("--date", help="Date to check (YYYY-MM-DD)", default=datetime.date.today().strftime("%Y-%m-%d"))
    parser.add_argument("--device", help="Device ID", default=os.getenv("MELCLOUD_DEVICE_ID"))
    args = parser.parse_args()
    
    date = datetime.datetime.strptime(args.date, "%Y-%m-%d").date()
    device_id = args.device
    
    print(f"\n=== MELCloud Energy Data Viewer ===")
    print(f"Checking data for date: {date}")
    print(f"Device ID: {device_id}")
    print("==================================\n")
    
    # Load credentials
    load_dotenv()
    username = os.getenv("MELCLOUD_USERNAME")
    password = os.getenv("MELCLOUD_PASSWORD")
    
    if not username or not password:
        print("Error: Missing MELCloud credentials in .env file")
        sys.exit(1)
    
    if not device_id:
        print("Error: No device ID provided or set in MELCLOUD_DEVICE_ID environment variable")
        sys.exit(1)
    
    # Authenticate
    print("Authenticating with MELCloud...")
    login_url = "https://app.melcloud.com/Mitsubishi.Wifi.Client/Login/ClientLogin"
    login_data = {
        "Email": username,
        "Password": password,
        "Language": 0,
        "AppVersion": "1.23.4.0",
        "Persist": True,
        "CaptchaResponse": None
    }
    
    try:
        login_response = requests.post(login_url, json=login_data)
        if login_response.status_code != 200:
            print(f"Authentication failed with status code: {login_response.status_code}")
            sys.exit(1)
        
        login_result = login_response.json()
        if "ErrorId" in login_result and login_result["ErrorId"] is not None:
            print(f"Authentication error: {login_result.get('ErrorMessage', 'Unknown error')}")
            sys.exit(1)
        
        context_key = login_result["LoginData"]["ContextKey"]
        print("Authentication successful!")
        
        # Get device list to find building ID
        print("Fetching devices...")
        headers = {"X-MitsContextKey": context_key}
        
        devices_response = requests.get("https://app.melcloud.com/Mitsubishi.Wifi.Client/User/ListDevices", 
                               headers=headers)
        
        if devices_response.status_code != 200:
            print(f"Failed to fetch devices: {devices_response.status_code}")
            sys.exit(1)
        
        buildings = devices_response.json()
        
        building_id = None
        device_name = None
        
        # Find the building ID for the target device
        for building in buildings:
            if "Structure" in building and "Devices" in building["Structure"]:
                for device in building["Structure"]["Devices"]:
                    if str(device.get("DeviceID")) == str(device_id):
                        building_id = building["ID"]
                        device_name = device.get("DeviceName")
                        break
        
        if not building_id:
            print(f"Device with ID {device_id} not found in any building")
            sys.exit(1)
        
        print(f"Found device: {device_name} (ID: {device_id}) in building ID: {building_id}")
        
        # Prepare date range for energy report
        from_date = date - datetime.timedelta(days=3)
        to_date = date + datetime.timedelta(days=1)
        
        # Get energy report
        print(f"Fetching energy report for date range: {from_date} to {to_date}...")
        
        energy_url = "https://app.melcloud.com/Mitsubishi.Wifi.Client/EnergyCost/Report"
        payload = {
            "DeviceId": int(device_id),
            "UseCurrency": False,
            "FromDate": f"{from_date.strftime('%Y-%m-%d')}T00:00:00",
            "ToDate": f"{to_date.strftime('%Y-%m-%d')}T00:00:00"
        }
        
        energy_response = requests.post(energy_url, headers=headers, json=payload)
        
        if energy_response.status_code != 200:
            print(f"Failed to fetch energy report: {energy_response.status_code}")
            sys.exit(1)
        
        energy_data = energy_response.json()
        
        # Save raw energy report
        with open(f"energy_report_raw_{date}.json", "w") as f:
            json.dump(energy_data, f, indent=2)
        print(f"Saved raw energy report to energy_report_raw_{date}.json")
        
        # Parse the energy data
        print("\n=== ENERGY DATA STRUCTURE ===")
        for key in energy_data.keys():
            if isinstance(energy_data[key], list):
                print(f"{key}: List with {len(energy_data[key])} items")
            else:
                print(f"{key}: {energy_data[key]}")
        
        print("\n=== DATE MAPPING ===")
        # Check Labels array, which indicates the dates
        if "Labels" in energy_data:
            print(f"Labels array: {energy_data['Labels']}")
            print(f"FromDate: {energy_data.get('FromDate')}")
            print(f"ToDate: {energy_data.get('ToDate')}")
            
            # For numerical labels (typical case), they're usually days of month
            # We need to find which position in the arrays corresponds to our target date
            target_day = date.day
            target_index = None
            
            labels = energy_data["Labels"]
            for i, label in enumerate(labels):
                if isinstance(label, (int, float)) and int(label) == target_day:
                    target_index = i
                    break
                elif isinstance(label, str) and str(target_day) in label:
                    target_index = i
                    break
            
            if target_index is not None:
                print(f"\nFound target date {date} at index {target_index}")
                
                # Extract energy values for this date
                print("\n=== ENERGY VALUES FOR TARGET DATE ===")
                
                if "Heating" in energy_data and target_index < len(energy_data["Heating"]):
                    heating_value = energy_data["Heating"][target_index]
                    print(f"Heating consumption: {heating_value} kWh")
                
                if "HotWater" in energy_data and target_index < len(energy_data["HotWater"]):
                    hotwater_value = energy_data["HotWater"][target_index]
                    print(f"Hot water consumption: {hotwater_value} kWh")
                
                if "ProducedHeating" in energy_data and target_index < len(energy_data["ProducedHeating"]):
                    prod_heating = energy_data["ProducedHeating"][target_index]
                    print(f"Heating production: {prod_heating} kWh")
                
                if "ProducedHotWater" in energy_data and target_index < len(energy_data["ProducedHotWater"]):
                    prod_hotwater = energy_data["ProducedHotWater"][target_index]
                    print(f"Hot water production: {prod_hotwater} kWh")
                
                if "CoP" in energy_data and target_index < len(energy_data["CoP"]):
                    cop_value = energy_data["CoP"][target_index]
                    print(f"COP: {cop_value}")
                
                # Calculate totals
                total_consumed = 0
                total_produced = 0
                
                if "Heating" in energy_data and target_index < len(energy_data["Heating"]):
                    total_consumed += float(energy_data["Heating"][target_index] or 0)
                
                if "HotWater" in energy_data and target_index < len(energy_data["HotWater"]):
                    total_consumed += float(energy_data["HotWater"][target_index] or 0)
                
                if "ProducedHeating" in energy_data and target_index < len(energy_data["ProducedHeating"]):
                    total_produced += float(energy_data["ProducedHeating"][target_index] or 0)
                
                if "ProducedHotWater" in energy_data and target_index < len(energy_data["ProducedHotWater"]):
                    total_produced += float(energy_data["ProducedHotWater"][target_index] or 0)
                
                print(f"\nTotal energy consumed: {total_consumed} kWh")
                print(f"Total energy produced: {total_produced} kWh")
                
                # Calculate COP manually if needed
                if total_consumed > 0:
                    calculated_cop = total_produced / total_consumed
                    print(f"Calculated COP: {calculated_cop:.2f}")
            else:
                print(f"\nTarget date {date} not found in the energy report")
                print("Available dates in the report:")
                for i, label in enumerate(labels):
                    print(f"  Index {i}: {label}")
                
        else:
            print("No Labels array found in energy report")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    main()
