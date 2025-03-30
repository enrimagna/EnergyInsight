#!/usr/bin/env python3
"""
Script to import temperature data from a CSV file into the energy_data table.
"""

import os
import csv
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

def import_temperature_data(csv_file_path):
    """Import temperature data from CSV file into the database."""
    # Load environment variables
    load_dotenv()
    
    # Get database connection
    db = Database()
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Counters for statistics
    total_rows = 0
    updated_rows = 0
    new_rows = 0
    
    try:
        # Open and read the CSV file
        with open(csv_file_path, 'r') as csv_file:
            csv_reader = csv.DictReader(csv_file)
            
            # Process each row
            for row in csv_reader:
                total_rows += 1
                
                # Extract date and temperature
                date_str = row['date']
                temperature = float(row['average_temperature'])
                
                # Check if a record exists for this date
                cursor.execute('SELECT id FROM energy_data WHERE date = ?', (date_str,))
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing record
                    cursor.execute('''
                    UPDATE energy_data 
                    SET outdoor_temp = ?
                    WHERE date = ?
                    ''', (temperature, date_str))
                    updated_rows += 1
                else:
                    # Insert new record with just temperature data
                    cursor.execute('''
                    INSERT INTO energy_data (date, outdoor_temp)
                    VALUES (?, ?)
                    ''', (date_str, temperature))
                    new_rows += 1
                
                # Commit every 50 rows to avoid large transactions
                if total_rows % 50 == 0:
                    conn.commit()
                    logger.info(f"Processed {total_rows} rows...")
        
        # Final commit
        conn.commit()
        
        logger.info(f"Import completed: {total_rows} total rows processed")
        logger.info(f"Updated {updated_rows} existing records")
        logger.info(f"Created {new_rows} new records")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error importing temperature data: {str(e)}")
        raise
    finally:
        # Close the database connection
        db.close_connection()

def main():
    """Main function to run the script."""
    csv_file_path = 'daily_average_temperature.csv'
    
    if not os.path.exists(csv_file_path):
        logger.error(f"CSV file not found: {csv_file_path}")
        print(f"Error: CSV file not found at {csv_file_path}")
        return
    
    logger.info(f"Starting import from {csv_file_path}...")
    
    # Confirm with user
    print(f"\nThis script will import temperature data from {csv_file_path}")
    print("into the energy_data table in your database.")
    print("Existing records will be updated, and new records will be created as needed.\n")
    
    confirmation = input("Do you want to proceed? (yes/no): ")
    
    if confirmation.lower() == 'yes':
        import_temperature_data(csv_file_path)
        print("\nImport completed successfully.")
    else:
        print("\nImport cancelled.")

if __name__ == "__main__":
    main()
