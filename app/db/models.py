import sqlite3
import os
import datetime
from pathlib import Path


class Database:
    def __init__(self, db_path=None):
        """Initialize database connection and ensure tables exist."""
        if db_path is None:
            # Default to the path specified in .env or a default location
            from dotenv import load_dotenv
            load_dotenv()
            db_path = os.getenv('DATABASE_PATH', 'app/db/energy_data.db')
        
        # Ensure directory exists
        Path(os.path.dirname(db_path)).mkdir(parents=True, exist_ok=True)
        
        self.db_path = db_path
        self.conn = None
        self.create_tables()
    
    def get_connection(self):
        """Get a database connection."""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        return self.conn
    
    def close_connection(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def create_tables(self):
        """Create database tables if they don't exist."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Energy usage data from MELCloud
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
        
        # Temperature data from Home Assistant
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS temperature_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL,
            indoor_temp REAL NOT NULL,
            outdoor_temp REAL NOT NULL,
            UNIQUE(timestamp)
        )
        ''')
        
        # Price information
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
    
    def add_energy_data(self, timestamp, power_consumption, energy_consumed, cost):
        """Add energy usage data from MELCloud."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            INSERT INTO energy_data (timestamp, power_consumption, energy_consumed, cost)
            VALUES (?, ?, ?, ?)
            ''', (timestamp, power_consumption, energy_consumed, cost))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Record already exists
            return False
    
    def add_temperature_data(self, timestamp, indoor_temp, outdoor_temp):
        """Add temperature data from Home Assistant."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            INSERT INTO temperature_data (timestamp, indoor_temp, outdoor_temp)
            VALUES (?, ?, ?)
            ''', (timestamp, indoor_temp, outdoor_temp))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Record already exists
            return False
    
    def update_prices(self, electricity_price, diesel_price, diesel_efficiency):
        """Update price information."""
        conn = self.get_connection()
        cursor = conn.cursor()
        timestamp = datetime.datetime.now()
        
        cursor.execute('''
        INSERT INTO prices (timestamp, electricity_price, diesel_price, diesel_efficiency)
        VALUES (?, ?, ?, ?)
        ''', (timestamp, electricity_price, diesel_price, diesel_efficiency))
        conn.commit()
    
    def get_energy_data(self, start_date, end_date):
        """Get energy data for the specified date range."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT timestamp, power_consumption, energy_consumed, cost FROM energy_data
        WHERE timestamp >= ? AND timestamp <= ?
        ORDER BY timestamp
        ''', (start_date, end_date))
        
        return cursor.fetchall()
    
    def get_temperature_data(self, start_date, end_date):
        """Get temperature data for the specified date range."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT timestamp, indoor_temp, outdoor_temp FROM temperature_data
        WHERE timestamp >= ? AND timestamp <= ?
        ORDER BY timestamp
        ''', (start_date, end_date))
        
        return cursor.fetchall()
    
    def get_current_prices(self):
        """Get the most recent price information."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT * FROM prices
        ORDER BY timestamp DESC
        LIMIT 1
        ''')
        
        return cursor.fetchone()
    
    def calculate_diesel_cost(self, start_date, end_date):
        """Calculate hypothetical diesel cost based on temperature data."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get price information
        prices = self.get_current_prices()
        if not prices:
            return None
        
        diesel_price = prices['diesel_price']
        diesel_efficiency = prices['diesel_efficiency']
        
        # Get temperature data
        cursor.execute('''
        SELECT * FROM temperature_data
        WHERE timestamp >= ? AND timestamp <= ?
        ORDER BY timestamp
        ''', (start_date, end_date))
        
        temp_data = cursor.fetchall()
        
        # Simple model: assume diesel consumption is proportional to 
        # the difference between indoor and outdoor temp
        total_cost = 0
        for data in temp_data:
            temp_diff = max(0, data['indoor_temp'] - data['outdoor_temp'])
            # Simple approximation: 0.1L of diesel per degree per hour
            diesel_consumed = 0.1 * temp_diff
            cost = diesel_consumed * diesel_price / diesel_efficiency
            total_cost += cost
        
        return total_cost
