import os
import datetime
import random
import sqlite3
import math
from pathlib import Path

# Ensure the database directory exists
db_dir = "app/db"
Path(db_dir).mkdir(parents=True, exist_ok=True)

# Database path
db_path = "app/db/energy_data.db"

# Connect to the database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create tables if they don't exist
cursor.execute('''
CREATE TABLE IF NOT EXISTS energy_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    power_consumption REAL NOT NULL,
    energy_consumed REAL NOT NULL,
    cost REAL NOT NULL,
    UNIQUE(timestamp)
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS temperature_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    indoor_temp REAL NOT NULL,
    outdoor_temp REAL NOT NULL,
    UNIQUE(timestamp)
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    electricity_price REAL NOT NULL,
    diesel_price REAL NOT NULL,
    diesel_efficiency REAL NOT NULL,
    UNIQUE(timestamp)
)
''')

conn.commit()

# Generate sample data for the past 30 days
end_date = datetime.datetime.now()
start_date = end_date - datetime.timedelta(days=30)
current_date = start_date

# Price information
electricity_price = 0.28  # per kWh
diesel_price = 1.50       # per liter
diesel_efficiency = 0.85  # efficiency factor

# Update prices
cursor.execute('''
INSERT OR REPLACE INTO prices (timestamp, electricity_price, diesel_price, diesel_efficiency)
VALUES (?, ?, ?, ?)
''', (datetime.datetime.now(), electricity_price, diesel_price, diesel_efficiency))

# Generate data points for each day
while current_date <= end_date:
    # For each day, generate 4 data points (every 6 hours)
    for hour in [0, 6, 12, 18]:
        timestamp = current_date.replace(hour=hour, minute=0, second=0, microsecond=0)
        
        # Energy data with daily and seasonal patterns
        day_factor = 1.0 + 0.2 * math.sin(hour * math.pi / 12)  # Daily pattern
        season_factor = 1.0 + 0.5 * math.sin((current_date.month - 1) * math.pi / 6)  # Seasonal pattern
        random_factor = random.uniform(0.8, 1.2)  # Random variation
        
        power_consumption = 1500 * day_factor * season_factor * random_factor  # Watts
        energy_consumed = power_consumption * 6 / 1000  # kWh over 6 hours
        cost = energy_consumed * electricity_price
        
        try:
            cursor.execute('''
            INSERT INTO energy_data (timestamp, power_consumption, energy_consumed, cost)
            VALUES (?, ?, ?, ?)
            ''', (timestamp, power_consumption, energy_consumed, cost))
        except sqlite3.IntegrityError:
            # Skip if record already exists
            pass
        
        # Temperature data with daily and seasonal patterns
        indoor_temp = 21.0 + random.uniform(-1.0, 1.0)  # Indoor temperature around 21°C
        
        # Outdoor temperature with seasonal and daily patterns
        seasonal_base = 15.0 - 10.0 * math.cos((current_date.month - 1) * math.pi / 6)  # Seasonal base temperature
        daily_variation = 5.0 * math.sin(hour * math.pi / 12)  # Daily temperature variation
        outdoor_temp = seasonal_base + daily_variation + random.uniform(-3.0, 3.0)  # Add some randomness
        
        try:
            cursor.execute('''
            INSERT INTO temperature_data (timestamp, indoor_temp, outdoor_temp)
            VALUES (?, ?, ?)
            ''', (timestamp, indoor_temp, outdoor_temp))
        except sqlite3.IntegrityError:
            # Skip if record already exists
            pass
    
    # Move to the next day
    current_date += datetime.timedelta(days=1)

conn.commit()
conn.close()

print(f"Generated test data in {db_path}")
