# Data Sources

## MELCloud Integration

The application fetches energy usage data from Mitsubishi Electric Cloud (MELCloud) using the `pymelcloud` library.

### Configuration
Add your MELCloud credentials to the `.env` file:
```
MELCLOUD_USERNAME=your_email@example.com
MELCLOUD_PASSWORD=your_password
```

### Implementation Details
- The `MELCloudFetcher` class in `app/data_fetchers.py` handles all MELCloud data retrieval
- Energy usage data is fetched using the `energy_report()` method of devices
- For development and testing purposes, a mock implementation (`MockMELCloudDevice`) is provided
- The mock implementation generates realistic energy consumption data when the real API is unavailable

## Home Assistant Integration

Temperature data is retrieved from Home Assistant via its REST API.

### Configuration
Add your Home Assistant connection details to the `.env` file:
```
HASS_URL=http://your-homeassistant:8123
HASS_TOKEN=your_long_lived_access_token
```

### Implementation Details
- The `HomeAssistantFetcher` class in `app/data_fetchers.py` handles all Home Assistant data retrieval
- The application looks for specific temperature sensors (`sensor.indoor_temperature` and `sensor.outdoor_temperature`)
- If Home Assistant is unavailable or sensors aren't found, mock temperature data is automatically generated

## Price Information

The application uses price information to calculate operating costs and compare with alternative heating methods.

### Configuration
Set your local energy prices in the `.env` file:
```
ELECTRICITY_PRICE=0.28
DIESEL_PRICE=1.50
DIESEL_EFFICIENCY=0.85
```

### Implementation Details
- The `update_prices()` function in `app/data_fetchers.py` handles price updates
- Prices are stored in the database and used for cost calculations
- The application compares heat pump electricity costs with hypothetical diesel heating costs