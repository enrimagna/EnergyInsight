# MELCloud API Information

## Authentication Process

The MELCloud API requires authentication through a multi-step process:

1. **Authentication Endpoint**: `https://app.melcloud.com/Mitsubishi.Wifi.Client/Login/ClientLogin`
2. **Authentication Method**: POST request with JSON payload
3. **Required Parameters**:
   - Email: Your MELCloud account email
   - Password: Your MELCloud account password
   - Language: 0 (for English)
   - AppVersion: Version string (e.g., "1.23.4.0")
   - Persist: true
   - CaptchaResponse: null

```json
{
  "Email": "your.email@example.com",
  "Password": "your_password",
  "Language": 0,
  "AppVersion": "1.23.4.0",
  "Persist": true,
  "CaptchaResponse": null
}
```

4. **Successful Authentication Response**:

```json
{
  "ErrorId": null,
  "ErrorMessage": null,
  "LoginStatus": 0,
  "UserId": 0,
  "RandomKey": null,
  "AppVersionAnnouncement": null,
  "LoginData": {
    "ContextKey": "0-XXXXXXXXXXXXXXXXXXXXXXXX-XXXXXX-X",
    "Client": XXXXXX,
    "Name": "Your Name",
    "CountryName": "France",
    "CurrencySymbol": "€",
    ...
  }
}
```

5. **Key Authentication Values**:
   - `ContextKey`: Required for all subsequent API calls (passed as `X-MitsContextKey` header)

## MELCloud API Structure and Data Flow

1. **Authentication** → 2. **List Buildings** → 3. **Access Devices** → 4. **Get Device Info & Energy Reports**

### Building and Device Structure

The MELCloud API organizes data hierarchically:

- **Buildings**: Top-level containers (e.g., "École de Chamoule")
  - **Devices**: Heat pumps and other equipment within buildings
    - **Device Data**: Current status and energy information

### Accessing Device Information

After authentication, follow these steps:

1. **Get Buildings List**: `https://app.melcloud.com/Mitsubishi.Wifi.Client/User/ListDevices`
   - Method: GET
   - Headers: `X-MitsContextKey: [your_context_key]`

2. **Get Device Details**: `https://app.melcloud.com/Mitsubishi.Wifi.Client/Device/Get`
   - Method: GET
   - Headers: `X-MitsContextKey: [your_context_key]`
   - Parameters:
     - `id`: Device ID from the buildings list
     - `buildingID`: Building ID from the buildings list

3. **Get Energy Reports**: `https://app.melcloud.com/Mitsubishi.Wifi.Client/EnergyCost/Report`
   - Method: POST
   - Headers: `X-MitsContextKey: [your_context_key]`
   - JSON Payload:
     ```json
     {
       "DeviceId": 119650321,
       "UseCurrency": false,
       "FromDate": "2025-03-17T00:00:00",
       "ToDate": "2025-03-21T00:00:00"
     }
     ```

## Available Data from MELCloud API

### Device Information

The device information includes comprehensive data about your heat pump:

```json
{
  "DeviceID": 119650321,
  "DeviceName": "Zuby",
  "SerialNumber": "2428213184",
  "MacAddress": "8c:53:e6:84:e9:79",
  "Device": {
    "Power": true,
    "OperationMode": 2,
    "RoomTemperatureZone1": 18.0,
    "OutdoorTemperature": 5.0,
    "FlowTemperature": 51.5,
    "ReturnTemperature": 49.5,
    "DemandPercentage": 10,
    "WaterPump1Status": true,
    "WaterPump2Status": true,
    "BoosterHeater1Status": false,
    "BoosterHeater2Status": false
  }
}
```

### Energy Consumption Data - IMPORTANT

**NOTE: Always use the Energy Report endpoint to retrieve accurate energy consumption data.**

While the device data response might include fields like `DailyHeatingEnergyConsumed`, these are often null or inaccurate. The Energy Report endpoint is the reliable source for energy consumption and production data.

#### Energy Report Structure

The Energy Report contains arrays of consumption and production values for each day in the requested date range:

```json
{
  "HotWater": [4.03, 1.8, 3.05, 3.09, 1.62],
  "Heating": [51.82, 48.3, 36.86, 27.57, 23.57],
  "ProducedHotWater": [8.86, 4.16, 6.43, 7.9, 4.41],
  "ProducedHeating": [115.37, 108.92, 84.49, 68.4, 62.74],
  "CoP": [2.22, 2.26, 2.28, 2.49, 2.67],
  "Labels": [17, 18, 19, 20, 21],
  "FromDate": "2025-03-17T00:00:00",
  "ToDate": "2025-03-21T00:00:00",
  "TotalHeatingConsumed": 188.12,
  "TotalHotWaterConsumed": 13.59,
  "TotalHeatingProduced": 439.92,
  "TotalHotWaterProduced": 31.76
}
```

#### Date Mapping in Energy Reports

The `Labels` array is crucial for mapping values to specific dates:

1. **Numeric Labels**: Most commonly, labels are day numbers (e.g., [17, 18, 19, 20, 21] for March 17-21)
2. **Position Matching**: The position in arrays like `Heating` and `HotWater` corresponds to the position in the `Labels` array
3. **Example**: If you want data for March 20th, you'd look for the position of "20" in the `Labels` array, then use that same position in the energy arrays

#### Implementation Example

```python
# Find index for target date (e.g., March 20th)
target_day = 20
target_index = None

for i, label in enumerate(energy_data["Labels"]):
    if label == target_day:
        target_index = i
        break

if target_index is not None:
    # Get energy values at that index
    heating_consumed = energy_data["Heating"][target_index]  # 27.57 kWh
    hot_water_consumed = energy_data["HotWater"][target_index]  # 3.09 kWh
    heating_produced = energy_data["ProducedHeating"][target_index]  # 68.4 kWh
    hot_water_produced = energy_data["ProducedHotWater"][target_index]  # 7.9 kWh
    cop = energy_data["CoP"][target_index]  # 2.49
```

#### Calculating Total Values

For any given date, you can calculate:

```python
# Total energy consumed and produced
total_consumed = heating_consumed + hot_water_consumed  # 30.66 kWh
total_produced = heating_produced + hot_water_produced  # 76.3 kWh

# Manually calculate COP if needed
calculated_cop = total_produced / total_consumed  # 2.49
```

### Key Data Points for Energy Monitoring

1. **Energy Consumption** (from Energy Report):
   - `Heating`: Daily heating energy consumed (kWh)
   - `HotWater`: Daily hot water energy consumed (kWh)
   - `ProducedHeating`: Daily heating energy produced (kWh)
   - `ProducedHotWater`: Daily hot water energy produced (kWh)
   - `CoP`: Daily Coefficient of Performance (efficiency)

2. **Temperature Data** (from Device Data):
   - `RoomTemperatureZone1`: Indoor temperature (°C)
   - `OutdoorTemperature`: Outdoor temperature (°C)
   - `FlowTemperature`: Flow temperature (°C)
   - `ReturnTemperature`: Return temperature (°C)

3. **Operational Status** (from Device Data):
   - `Power`: Device power status (true/false)
   - `OperationMode`: Operating mode (0=Heat, 1=Dry, 2=Cool, 3=Vent, 4=Auto)
   - `DemandPercentage`: Current demand percentage (%)

### Calculating Efficiency (COP)

The Coefficient of Performance (COP) can be calculated as:
```
COP = (HeatingEnergyProduced + HotWaterEnergyProduced) / (HeatingEnergyConsumed + HotWaterEnergyConsumed)
```

For example, using values from the Energy Report:
```
COP = (68.4 + 7.9) / (27.57 + 3.09) = 76.3 / 30.66 = 2.49
```

## Updated Database Schema

Based on the available MELCloud data, we've updated the database schema to store comprehensive energy information:

```sql
CREATE TABLE IF NOT EXISTS energy_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    heating_energy_consumed REAL,
    hot_water_energy_consumed REAL,
    total_energy_consumed REAL,
    heating_energy_produced REAL,
    hot_water_energy_produced REAL,
    total_energy_produced REAL,
    cop REAL,
    power_consumption REAL,
    cost REAL,
    device_id INTEGER,
    device_name TEXT,
    operation_mode TEXT,
    demand_percentage INTEGER,
    UNIQUE(date)
)
```

```sql
CREATE TABLE IF NOT EXISTS temperature_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    indoor_temp REAL NOT NULL,
    outdoor_temp REAL NOT NULL,
    flow_temp REAL,
    return_temp REAL,
    UNIQUE(date)
)
```

## Implementation Notes

1. **Data Frequency**: MELCloud provides daily energy data, which aligns with our requirement to store one value per day.

2. **Authentication Challenges**: 
   - Different `AppVersion` values may work better for authentication
   - We've had success with versions "1.23.4.0" and "1.19.1.1"
   - The API may occasionally return HTML instead of JSON, indicating temporary unavailability

3. **Alternative Libraries**:
   - The `pymelcloud` Python library provides a wrapper for the MELCloud API
   - Direct REST API calls with the `requests` library offer more control

4. **Data Storage Process**:
   - Extract data from MELCloud API daily
   - Calculate derived values (total consumption, COP, cost)
   - Store in database with one record per day

## Scripts for Accessing MELCloud API

We've created several scripts to interact with the MELCloud API:

1. `test_melcloud_raw.py`: Tests authentication and retrieves raw API responses
2. `extract_melcloud_data.py`: Extracts and formats data from the MELCloud API
3. `fetch_melcloud_to_db.py`: Stores the extracted data in the database

## Recommended Approach for Production

For reliable daily data collection:

1. Schedule `fetch_melcloud_to_db.py` to run once per day (after midnight)
2. Implement robust error handling for API unavailability
3. Consider implementing a retry mechanism for failed API calls
4. Log all API interactions for troubleshooting

By following this approach, you'll have a reliable system for monitoring your heat pump's energy usage and calculating costs compared to alternative heating methods.
