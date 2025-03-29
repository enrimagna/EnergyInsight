#!/usr/bin/env python
"""
Database migration script for EnergyInsight.
This script updates the prices table schema from using a date column to using year and month columns.
"""

import sqlite3
import os
import datetime
import logging
from pathlib import Path
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate_database():
    """Migrate the database schema."""
    # Load environment variables
    load_dotenv()
    db_path = os.getenv('DATABASE_PATH', 'app/db/energy_data.db')
    
    # Ensure directory exists
    Path(os.path.dirname(db_path)).mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Migrating database at: {db_path}")
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Check if the old prices table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='prices'")
        table_exists = cursor.fetchone()
        
        if table_exists:
            logger.info("Found existing prices table, checking schema...")
            
            # Check if the old schema is being used (with date column)
            cursor.execute("PRAGMA table_info(prices)")
            columns = cursor.fetchall()
            column_names = [col['name'] for col in columns]
            
            if 'date' in column_names and 'year' not in column_names:
                logger.info("Old schema detected, migrating data...")
                
                # Get existing price data
                cursor.execute("SELECT * FROM prices")
                old_prices = cursor.fetchall()
                
                # Create a temporary table with the new schema
                cursor.execute('''
                CREATE TABLE prices_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    year INTEGER NOT NULL,
                    month INTEGER NOT NULL,
                    electricity_price REAL NOT NULL,
                    diesel_price REAL NOT NULL,
                    diesel_efficiency REAL NOT NULL,
                    UNIQUE(year, month)
                )
                ''')
                
                # Migrate data to the new schema
                for price in old_prices:
                    if isinstance(price['date'], str):
                        date_obj = datetime.datetime.strptime(price['date'], '%Y-%m-%d').date()
                    else:
                        date_obj = price['date']
                    
                    year = date_obj.year
                    month = date_obj.month
                    
                    cursor.execute('''
                    INSERT INTO prices_new (year, month, electricity_price, diesel_price, diesel_efficiency)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (year, month, price['electricity_price'], price['diesel_price'], price['diesel_efficiency']))
                
                # Drop the old table and rename the new one
                cursor.execute("DROP TABLE prices")
                cursor.execute("ALTER TABLE prices_new RENAME TO prices")
                
                logger.info(f"Successfully migrated {len(old_prices)} price records to the new schema")
            elif 'year' in column_names and 'month' in column_names:
                logger.info("Database already using the new schema with year and month columns")
            else:
                logger.warning("Unexpected schema detected in prices table")
        else:
            logger.info("No existing prices table found, creating with new schema...")
            # Create the prices table with the new schema
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
            
            # Add default price for current month
            today = datetime.datetime.now()
            cursor.execute('''
            INSERT OR REPLACE INTO prices (year, month, electricity_price, diesel_price, diesel_efficiency)
            VALUES (?, ?, ?, ?, ?)
            ''', (today.year, today.month, 0.28, 1.50, 0.85))
            
            logger.info("Created new prices table with default values")
        
        # Commit the changes
        conn.commit()
        logger.info("Database migration completed successfully")
        
    except Exception as e:
        logger.error(f"Error during migration: {str(e)}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()
