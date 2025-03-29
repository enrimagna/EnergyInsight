# Database Structure and Management

The application uses SQLite for data storage, which provides a simple, file-based database solution that requires no additional services.

## Database Location

The database file is stored at the location specified in the `.env` file:
```
DATABASE_PATH=app/db/energy_data.db
```

## Database Schema

The database consists of three main tables:

### 1. energy_data
Stores energy usage data collected from MELCloud:
```sql
CREATE TABLE energy_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    power_consumption REAL NOT NULL,
    energy_consumed REAL NOT NULL,
    cost REAL NOT NULL,
    UNIQUE(timestamp)
)
```

### 2. temperature_data
Stores temperature readings collected from Home Assistant:
```sql
CREATE TABLE temperature_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    indoor_temp REAL NOT NULL,
    outdoor_temp REAL NOT NULL,
    UNIQUE(timestamp)
)
```

### 3. prices
Stores price information for cost calculations:
```sql
CREATE TABLE prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    electricity_price REAL NOT NULL,
    diesel_price REAL NOT NULL,
    diesel_efficiency REAL NOT NULL,
    UNIQUE(timestamp)
)
```

## Database Management

The database is managed through the `Database` class in `app/db/models.py`, which provides methods for:

- Creating database tables
- Adding energy and temperature data
- Retrieving data for analysis and visualization
- Updating price information
- Calculating comparative costs

The database is automatically created when the application starts, and test data is generated if the database is empty.