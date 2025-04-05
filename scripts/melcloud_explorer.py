#!/usr/bin/env python3
"""
MELCloud Explorer - Query all available data from a MELCloud device using PyMELCloud
"""
import os
import sys
import asyncio
import json
from datetime import datetime, timedelta
import argparse
from dotenv import load_dotenv
import aiohttp

async def main(email, password, device_id=None):
    """Main function to explore MELCloud device data"""
    print("MELCloud Explorer")
    print("=================")
    print(f"Logging in with account: {email}")
    
    async with aiohttp.ClientSession() as session:
        # Login to MELCloud
        print("Authenticating...")
        
        # Perform login using direct API calls since we don't have pymelcloud installed
        login_url = "https://app.melcloud.com/Mitsubishi.Wifi.Client/Login/ClientLogin"
        login_data = {
            "Email": email,
            "Password": password,
            "Language": 0,
            "AppVersion": "1.23.4.0",
            "Persist": True,
            "CaptchaResponse": None
        }
        
        async with session.post(login_url, json=login_data) as resp:
            if resp.status != 200:
                print(f"Authentication failed: {resp.status}")
                return
            
            login_result = await resp.json()
            if "ErrorId" in login_result and login_result["ErrorId"] is not None:
                print(f"Authentication error: {login_result.get('ErrorMessage', 'Unknown error')}")
                return
            
            context_key = login_result["LoginData"]["ContextKey"]
            print("Authentication successful!")
            
            # Get device list
            print("Fetching devices...")
            headers = {"X-MitsContextKey": context_key}
            
            async with session.get("https://app.melcloud.com/Mitsubishi.Wifi.Client/User/ListDevices", 
                                 headers=headers) as resp:
                if resp.status != 200:
                    print(f"Failed to fetch devices: {resp.status}")
                    return
                
                buildings = await resp.json()
                
                all_devices = []
                for building in buildings:
                    building_id = building.get("ID")
                    building_name = building.get("Name")
                    
                    print(f"\nBuilding: {building_name} (ID: {building_id})")
                    
                    if "Structure" not in building or "Devices" not in building["Structure"]:
                        print("  No devices found in this building")
                        continue
                    
                    devices = building["Structure"]["Devices"]
                    if not devices:
                        print("  No devices found in this building")
                        continue
                    
                    print(f"  Found {len(devices)} device(s)")
                    
                    for device in devices:
                        device_id_found = device.get("DeviceID")
                        device_name = device.get("DeviceName")
                        device_type = device.get("Device", {}).get("DeviceType")
                        
                        device_type_names = {
                            0: "Air-to-Air Heat Pump (ATA)",
                            1: "Air-to-Water Heat Pump (ATW)",
                            3: "Energy Recovery Ventilator (ERV)",
                        }
                        
                        device_type_name = device_type_names.get(device_type, f"Unknown Type ({device_type})")
                        
                        print(f"  - Device: {device_name} (ID: {device_id_found}, Type: {device_type_name})")
                        
                        all_devices.append({
                            "id": device_id_found,
                            "name": device_name,
                            "type": device_type,
                            "type_name": device_type_name,
                            "building_id": building_id
                        })
            
                if device_id:
                    # Find specific device
                    target_device = next((d for d in all_devices if d["id"] == int(device_id)), None)
                    if not target_device:
                        print(f"\nTarget device ID {device_id} not found!")
                        return
                else:
                    # Just use the first device
                    if not all_devices:
                        print("\nNo devices found!")
                        return
                    target_device = all_devices[0]
            
            # Get device data
            print(f"\nQuerying data for device: {target_device['name']} (ID: {target_device['id']})")
            
            device_url = f"https://app.melcloud.com/Mitsubishi.Wifi.Client/Device/Get"
            params = {
                "id": target_device["id"],
                "buildingID": target_device["building_id"]
            }
            
            async with session.get(device_url, headers=headers, params=params) as resp:
                if resp.status != 200:
                    print(f"Failed to fetch device data: {resp.status}")
                    return
                
                device_data = await resp.json()
                
                # Save raw device data
                with open(f"device_data_raw_{target_device['id']}.json", "w") as f:
                    json.dump(device_data, f, indent=2)
                print(f"Raw device data saved to device_data_raw_{target_device['id']}.json")
                
                # Display key device information
                print("\nDevice Information:")
                print(f"  Name: {target_device['name']}")
                print(f"  Type: {target_device['type_name']}")
                print(f"  Power: {'On' if device_data.get('Power') else 'Off'}")
                print(f"  Last Communication: {device_data.get('LastCommunication')}")
                
                # Get energy report
                print("\nFetching energy reports...")
                
                # Get reports for the past week
                today = datetime.now()
                from_date = today - timedelta(days=7)
                to_date = today + timedelta(days=1)  # Include today
                
                energy_url = "https://app.melcloud.com/Mitsubishi.Wifi.Client/EnergyCost/Report"
                energy_payload = {
                    "DeviceId": target_device["id"],
                    "UseCurrency": False,
                    "FromDate": f"{from_date.strftime('%Y-%m-%d')}T00:00:00",
                    "ToDate": f"{to_date.strftime('%Y-%m-%d')}T00:00:00"
                }
                
                async with session.post(energy_url, headers=headers, json=energy_payload) as resp:
                    if resp.status != 200:
                        print(f"Failed to fetch energy report: {resp.status}")
                    else:
                        energy_data = await resp.json()
                        with open(f"energy_report_{target_device['id']}.json", "w") as f:
                            json.dump(energy_data, f, indent=2)
                        print(f"Energy report saved to energy_report_{target_device['id']}.json")
                        
                        # Display energy data structure
                        print("\nEnergy Report Structure:")
                        for key in energy_data.keys():
                            print(f"  - {key}")
                            if isinstance(energy_data[key], list):
                                print(f"    (List with {len(energy_data[key])} items)")
                                if energy_data[key] and isinstance(energy_data[key][0], dict):
                                    print(f"    Sample keys: {list(energy_data[key][0].keys())}")
                            elif isinstance(energy_data[key], dict):
                                print(f"    (Dictionary with keys: {list(energy_data[key].keys())})")
                
                # For ATW devices, get daily consumption values
                if target_device["type"] == 1:  # ATW
                    print("\nATW Device - Getting daily consumption values...")
                    
                    # Try to access consumption data through various API paths
                    # 1. Check device data for energy fields
                    energy_fields = [
                        "DailyHeatingEnergyConsumed", "DailyHeatingEnergyProduced",
                        "DailyHotWaterEnergyConsumed", "DailyHotWaterEnergyProduced",
                        "CurrentEnergyConsumed", "CurrentEnergyProduced"
                    ]
                    
                    print("\nEnergy fields in device data:")
                    for field in energy_fields:
                        print(f"  {field}: {device_data.get(field)}")
                    
                    # 2. Try getting daily consumption report for specific date
                    for day_offset in range(7, 0, -1):
                        test_date = today - timedelta(days=day_offset)
                        date_str = test_date.strftime("%Y-%m-%d")
                        
                        daily_params = {
                            "id": target_device["id"],
                            "buildingID": target_device["building_id"],
                            "date": date_str
                        }
                        
                        print(f"\nTesting date: {date_str}")
                        async with session.get(device_url, headers=headers, params=daily_params) as resp:
                            if resp.status != 200:
                                print(f"  Failed to fetch device data for {date_str}: {resp.status}")
                                continue
                            
                            daily_data = await resp.json()
                            print(f"  Data retrieved for {date_str}")
                            
                            energy_values = {k: daily_data.get(k) for k in energy_fields if k in daily_data}
                            if energy_values:
                                print(f"  Energy data found: {energy_values}")
                                with open(f"device_data_{date_str}.json", "w") as f:
                                    json.dump(daily_data, f, indent=2)
                                print(f"  Data saved to device_data_{date_str}.json")
                            else:
                                print("  No energy data fields found in daily device data")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MELCloud Explorer - Query all available data from a MELCloud device")
    parser.add_argument("--device-id", type=str, help="Specific device ID to query (optional)")
    args = parser.parse_args()
    
    load_dotenv()
    
    email = os.getenv('MELCLOUD_USERNAME')
    password = os.getenv('MELCLOUD_PASSWORD')
    
    if not email or not password:
        print("Error: MELCloud credentials not found. Please set MELCLOUD_USERNAME and MELCLOUD_PASSWORD in .env file")
        sys.exit(1)
    
    asyncio.run(main(email, password, args.device_id))
