import sqlite3
import os
import datetime
import logging
from pathlib import Path


logger = logging.getLogger(__name__)

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
        ''')
        
        # Temperature data from Home Assistant
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS temperature_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL,
            indoor_temp REAL NOT NULL,
            outdoor_temp REAL NOT NULL,
            flow_temp REAL,
            return_temp REAL,
            UNIQUE(date)
        )
        ''')
        
        # Price information - modified to include year and month
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            electricity_price REAL NOT NULL,
            diesel_price REAL NOT NULL,
            diesel_efficiency REAL NOT NULL,
            UNIQUE(year, month)
        )
        ''')
        
        conn.commit()
    
    def add_melcloud_data(self, date, heating_consumed, hot_water_consumed, heating_produced, 
                          hot_water_produced, cop, power_consumption, cost, device_id, 
                          device_name, operation_mode, demand_percentage):
        """Add energy usage data from MELCloud."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Calculate total energy consumed and produced
        total_consumed = (heating_consumed or 0) + (hot_water_consumed or 0)
        total_produced = (heating_produced or 0) + (hot_water_produced or 0)
        
        try:
            cursor.execute('''
            INSERT OR REPLACE INTO energy_data (
                date, heating_energy_consumed, hot_water_energy_consumed, 
                total_energy_consumed, heating_energy_produced, hot_water_energy_produced, 
                total_energy_produced, cop, power_consumption, cost, 
                device_id, device_name, operation_mode, demand_percentage
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                date, heating_consumed, hot_water_consumed, 
                total_consumed, heating_produced, hot_water_produced, 
                total_produced, cop, power_consumption, cost, 
                device_id, device_name, operation_mode, demand_percentage
            ))
            conn.commit()
            return True
        except sqlite3.IntegrityError as e:
            logger.error(f"Error adding MELCloud data: {e}")
            return False
    
    def add_energy_data(self, timestamp, power_consumption, energy_consumed, cost):
        """Add energy usage data from MELCloud (legacy method)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Convert timestamp to date
        if isinstance(timestamp, str):
            date = datetime.datetime.fromisoformat(timestamp).date()
        elif isinstance(timestamp, datetime.datetime):
            date = timestamp.date()
        else:
            date = timestamp  # Assume it's already a date
        
        try:
            cursor.execute('''
            INSERT OR REPLACE INTO energy_data (date, total_energy_consumed, power_consumption, cost)
            VALUES (?, ?, ?, ?)
            ''', (date, energy_consumed, power_consumption, cost))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Record already exists
            return False
    
    def add_temperature_data(self, timestamp, indoor_temp, outdoor_temp, flow_temp=None, return_temp=None):
        """Add temperature data from Home Assistant or MELCloud."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Convert timestamp to date
        if isinstance(timestamp, str):
            date = datetime.datetime.fromisoformat(timestamp).date()
        elif isinstance(timestamp, datetime.datetime):
            date = timestamp.date()
        else:
            date = timestamp  # Assume it's already a date
        
        try:
            cursor.execute('''
            INSERT OR REPLACE INTO temperature_data (date, indoor_temp, outdoor_temp, flow_temp, return_temp)
            VALUES (?, ?, ?, ?, ?)
            ''', (date, indoor_temp, outdoor_temp, flow_temp, return_temp))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Record already exists
            return False
    
    def update_prices(self, electricity_price, diesel_price, diesel_efficiency, year=None, month=None):
        """Update price information for a specific month and year.
        
        If year and month are not provided, uses the current month and year.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if year is None or month is None:
            today = datetime.datetime.now()
            year = today.year
            month = today.month
        
        # Log the values before inserting into the database
        logger.info(f"DB update_prices received - Year: {year}, Month: {month}, "
                   f"Electricity: {electricity_price} (type: {type(electricity_price)}), "
                   f"Diesel: {diesel_price} (type: {type(diesel_price)}), "
                   f"Efficiency: {diesel_efficiency} (type: {type(diesel_efficiency)})")
        
        cursor.execute('''
        INSERT OR REPLACE INTO prices (year, month, electricity_price, diesel_price, diesel_efficiency)
        VALUES (?, ?, ?, ?, ?)
        ''', (year, month, electricity_price, diesel_price, diesel_efficiency))
        conn.commit()
        
        # Verify the insertion
        cursor.execute('SELECT * FROM prices WHERE year = ? AND month = ?', (year, month))
        last_row = cursor.fetchone()
        if last_row:
            logger.info(f"Inserted price row - ID: {last_row['id']}, "
                       f"Year: {last_row['year']}, Month: {last_row['month']}, "
                       f"Electricity: {last_row['electricity_price']}, "
                       f"Diesel: {last_row['diesel_price']}, "
                       f"Efficiency: {last_row['diesel_efficiency']}")
        else:
            logger.warning("Failed to retrieve the last inserted row")
    
    def get_energy_data(self, start_date, end_date, energy_type='total'):
        """Get energy data for the specified date range and energy type."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Determine which energy columns to select based on energy_type
        if energy_type.lower() == 'heating':
            energy_consumed_col = 'heating_energy_consumed'
            energy_produced_col = 'heating_energy_produced'
        elif energy_type.lower() == 'hot_water':
            energy_consumed_col = 'hot_water_energy_consumed'
            energy_produced_col = 'hot_water_energy_produced'
        else:  # default to total
            energy_consumed_col = 'total_energy_consumed'
            energy_produced_col = 'total_energy_produced'
        
        cursor.execute(f'''
        SELECT date, {energy_consumed_col}, {energy_produced_col},
               cop, power_consumption, cost, operation_mode
        FROM energy_data
        WHERE date >= ? AND date <= ?
        ORDER BY date
        ''', (start_date, end_date))
        
        return cursor.fetchall()
    
    def get_temperature_data(self, start_date, end_date):
        """Get temperature data for the specified date range."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT date, indoor_temp, outdoor_temp, flow_temp, return_temp 
        FROM temperature_data
        WHERE date >= ? AND date <= ?
        ORDER BY date
        ''', (start_date, end_date))
        
        return cursor.fetchall()
    
    def get_current_prices(self):
        """Get the price information for the current month and year."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        today = datetime.datetime.now()
        
        cursor.execute('''
        SELECT * FROM prices
        WHERE year = ? AND month = ?
        ''', (today.year, today.month))
        
        result = cursor.fetchone()
        
        # If no price found for current month, try to get the most recent price
        if not result:
            cursor.execute('''
            SELECT * FROM prices
            ORDER BY year DESC, month DESC
            LIMIT 1
            ''')
            result = cursor.fetchone()
        
        # Log the retrieved values
        if result:
            logger.info(f"get_current_prices retrieved - ID: {result['id']}, "
                       f"Year: {result['year']}, Month: {result['month']}, "
                       f"Electricity: {result['electricity_price']}, "
                       f"Diesel: {result['diesel_price']}, "
                       f"Efficiency: {result['diesel_efficiency']}")
        else:
            logger.warning("No price data found in the database")
            
        return result
    
    def get_prices_for_month(self, year, month):
        """Get price information for a specific month and year."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT * FROM prices
        WHERE year = ? AND month = ?
        ''', (year, month))
        
        result = cursor.fetchone()
        
        # If no price found for specified month, get the most recent previous month
        if not result:
            # Try to find the most recent price before the requested month
            cursor.execute('''
            SELECT * FROM prices
            WHERE (year < ? OR (year = ? AND month < ?))
            ORDER BY year DESC, month DESC
            LIMIT 1
            ''', (year, year, month))
            result = cursor.fetchone()
            
            # If still no price, try any price (future prices)
            if not result:
                cursor.execute('''
                SELECT * FROM prices
                ORDER BY year DESC, month DESC
                LIMIT 1
                ''')
                result = cursor.fetchone()
        
        return result
    
    def get_all_prices(self):
        """Get all price records ordered by year and month."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT * FROM prices
        ORDER BY year DESC, month DESC
        ''')
        
        return cursor.fetchall()
    
    def calculate_diesel_cost(self, start_date, end_date):
        """Calculate hypothetical diesel cost based on energy produced data."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get energy production data for the date range
        cursor.execute('''
        SELECT date, total_energy_produced FROM energy_data
        WHERE date >= ? AND date <= ?
        ORDER BY date
        ''', (start_date, end_date))
        
        energy_data = cursor.fetchall()
        
        total_cost = 0
        
        for data in energy_data:
            date_str = data['date']
            if isinstance(date_str, str):
                date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            else:
                date = date_str
                
            year = date.year
            month = date.month
            
            # Get prices for this month
            price_data = self.get_prices_for_month(year, month)
            
            if not price_data:
                continue  # Skip if no price data available
                
            diesel_price = price_data['diesel_price']
            diesel_efficiency = price_data['diesel_efficiency']
            
            # Use formula from the cost_calculations.md document
            energy_produced = data['total_energy_produced'] or 0
            diesel_cost = (energy_produced / (diesel_efficiency * 10.5)) * diesel_price
            
            total_cost += diesel_cost
        
        return total_cost
        
    def calculate_electricity_cost(self, date, consumed_kwh):
        """Calculate electricity cost based on consumption and price for the given date."""
        if isinstance(date, str):
            date = datetime.datetime.strptime(date, '%Y-%m-%d').date()
            
        year = date.year
        month = date.month
        
        # Get prices for this month
        price_data = self.get_prices_for_month(year, month)
        
        if not price_data:
            # Default price if no data available
            return consumed_kwh * 0.28
            
        electricity_price = price_data['electricity_price']
        
        # Formula from cost_calculations.md: Cost = Consumption * Price
        return consumed_kwh * electricity_price

    def recalculate_energy_costs(self, start_date=None, end_date=None):
        """Recalculate all energy costs based on current price data."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get date range to update
        if not start_date:
            cursor.execute('SELECT MIN(date) FROM energy_data')
            result = cursor.fetchone()
            if result and result[0]:
                start_date = result[0]
            else:
                return False  # No data to update
                
        if not end_date:
            cursor.execute('SELECT MAX(date) FROM energy_data')
            result = cursor.fetchone()
            if result and result[0]:
                end_date = result[0]
            else:
                return False  # No data to update
        
        # Get all energy data records in the range
        cursor.execute('''
        SELECT id, date, total_energy_consumed FROM energy_data
        WHERE date >= ? AND date <= ?
        ''', (start_date, end_date))
        
        records = cursor.fetchall()
        
        # Update each record with the new cost
        for record in records:
            record_id = record['id']
            date = record['date']
            consumed = record['total_energy_consumed'] or 0
            
            new_cost = self.calculate_electricity_cost(date, consumed)
            
            cursor.execute('''
            UPDATE energy_data SET cost = ? WHERE id = ?
            ''', (new_cost, record_id))
        
        conn.commit()
        return True
