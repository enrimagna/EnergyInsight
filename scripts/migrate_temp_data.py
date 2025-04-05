#!/usr/bin/env python3
"""
Migration script to move temperature data from temperature_data table to energy_data table.
This script will:
1. Add temperature columns to energy_data table
2. Migrate existing temperature data to energy_data table
3. Drop the temperature_data table
"""

import os
import sqlite3
import logging
from datetime import datetime
from dotenv import load_dotenv
from app.db.models import Database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def migrate_database():
    """Perform the database migration."""
    # Load environment variables
    load_dotenv()
    
    # Get database connection
    db = Database()
    conn = db.get_connection()
    cursor = conn.cursor()
    
    try:
        # Start transaction
        conn.execute("BEGIN TRANSACTION")
        
        # Step 1: Add temperature columns to energy_data table
        logger.info("Adding temperature columns to energy_data table...")
        cursor.execute('''
        ALTER TABLE energy_data ADD COLUMN outdoor_temp REAL;
        ''')
        
        # Step 2: Migrate data from temperature_data to energy_data
        logger.info("Migrating temperature data to energy_data table...")
        cursor.execute('''
        SELECT * FROM temperature_data
        ''')
        temp_data = cursor.fetchall()
        
        # Count of records updated
        updated_count = 0
        missing_count = 0
        
        for record in temp_data:
            date = record['date']
            outdoor_temp = record['outdoor_temp']
            
            # Update energy_data record for this date
            cursor.execute('''
            UPDATE energy_data
            SET outdoor_temp = ?
            WHERE date = ?
            ''', (outdoor_temp, date))
            
            if cursor.rowcount > 0:
                updated_count += 1
            else:
                # If no matching energy_data record exists, create one with just temperature
                cursor.execute('''
                INSERT OR IGNORE INTO energy_data (date, outdoor_temp)
                VALUES (?, ?)
                ''', (date, outdoor_temp))
                missing_count += 1
        
        logger.info(f"Updated {updated_count} existing records with temperature data")
        logger.info(f"Created {missing_count} new records for dates with only temperature data")
        
        # Step 3: Drop the temperature_data table
        logger.info("Dropping temperature_data table...")
        cursor.execute('''
        DROP TABLE temperature_data
        ''')
        
        # Commit the transaction
        conn.commit()
        logger.info("Migration completed successfully")
        
    except Exception as e:
        # Rollback in case of error
        conn.rollback()
        logger.error(f"Migration failed: {str(e)}")
        raise
    finally:
        # Close the connection
        db.close_connection()

def main():
    """Main function to run the migration."""
    logger.info("Starting temperature data migration...")
    
    # Confirm with user
    print("\nWARNING: This script will migrate temperature data from temperature_data table")
    print("to energy_data table and then drop the temperature_data table.")
    print("This operation cannot be undone.\n")
    
    confirmation = input("Do you want to proceed? (yes/no): ")
    
    if confirmation.lower() == 'yes':
        migrate_database()
        print("\nMigration completed. The database schema has been updated.")
    else:
        print("\nMigration cancelled.")

if __name__ == "__main__":
    main()