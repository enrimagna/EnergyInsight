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

def validate_row(row):
    """Validate a row of data from the CSV file."""
    # Check if date exists
    if 'date' not in row or not row['date']:
        logger.warning("Skipping row: missing date")
        return False, None, None
        
    # Check if temperature exists
    if 'average_temperature' not in row or not row['average_temperature']:
        logger.warning(f"Skipping row for {row['date']}: missing temperature")
        return False, None, None
        
    # Validate date format
    try:
        date = datetime.strptime(row['date'], '%Y-%m-%d').date()
    except ValueError:
        logger.warning(f"Skipping row: invalid date format: {row['date']}")
        return False, None, None
        
    # Validate temperature value
    try:
        temperature = float(row['average_temperature'])
    except ValueError:
        logger.warning(f"Skipping row for {row['date']}: invalid temperature value: {row['average_temperature']}")
        return False, None, None
        
    # Check for reasonable temperature range (-50°C to +50°C)
    if temperature < -50 or temperature > 50:
        logger.warning(f"Suspicious temperature value for {row['date']}: {temperature}°C")
        # We'll still return True but log a warning
        
    return True, date, temperature

def import_temperature_data(csv_file_path, dry_run=False):
    """Import temperature data from CSV file into the database."""
    # Load environment variables
    load_dotenv()
    
    # Get database connection
    db = Database()
    conn = db.get_connection()
    
    # Counters for statistics
    total_rows = 0
    valid_rows = 0
    skipped_rows = 0
    updated_rows = 0
    new_rows = 0
    unchanged_rows = 0
    error_rows = 0
    
    try:
        # Open and read the CSV file
        with open(csv_file_path, 'r') as csv_file:
            csv_reader = csv.DictReader(csv_file)
            
            # Process each row
            for row in csv_reader:
                total_rows += 1
                
                # Validate the row
                is_valid, date, temperature = validate_row(row)
                
                if not is_valid:
                    skipped_rows += 1
                    continue
                    
                valid_rows += 1
                
                # If this is a dry run, just count the row
                if dry_run:
                    continue
                
                # Add to database
                success = db.add_temperature_data(date, temperature)
                
                # Check the database log to determine what happened
                if success:
                    # Check if it was a new row or an update
                    # This is a bit of a hack, but we can check the last log message
                    last_log = logging.root.handlers[0].formatter.format(logging.LogRecord(
                        "app.db.models", logging.INFO, "", 0, "", (), None))
                    
                    if "Skipping update" in last_log:
                        unchanged_rows += 1
                    elif "Updated temperature" in last_log:
                        updated_rows += 1
                    elif "Added new temperature" in last_log:
                        new_rows += 1
                else:
                    error_rows += 1
                
                # Commit every 50 rows to avoid large transactions
                if valid_rows % 50 == 0:
                    conn.commit()
                    logger.info(f"Processed {valid_rows} valid rows out of {total_rows} total rows...")
        
        # Final commit
        if not dry_run:
            conn.commit()
        
        logger.info(f"Import {'simulation' if dry_run else 'completed'}: {total_rows} total rows processed")
        logger.info(f"Valid rows: {valid_rows}, Skipped rows: {skipped_rows}")
        
        if not dry_run:
            logger.info(f"New records: {new_rows}, Updated records: {updated_rows}, Unchanged records: {unchanged_rows}, Errors: {error_rows}")
        
    except Exception as e:
        if not dry_run:
            conn.rollback()
        logger.error(f"Error importing temperature data: {str(e)}")
        raise
    finally:
        # Close the database connection
        db.close_connection()
        
    return {
        'total_rows': total_rows,
        'valid_rows': valid_rows,
        'skipped_rows': skipped_rows,
        'new_rows': new_rows,
        'updated_rows': updated_rows,
        'unchanged_rows': unchanged_rows,
        'error_rows': error_rows
    }

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
    
    # Ask if user wants to do a dry run first
    dry_run_response = input("Would you like to do a dry run first to validate the data? (yes/no): ")
    dry_run = dry_run_response.lower() == 'yes'
    
    if dry_run:
        print("\nPerforming dry run to validate data...")
        stats = import_temperature_data(csv_file_path, dry_run=True)
        
        print(f"\nDry run results:")
        print(f"Total rows in CSV: {stats['total_rows']}")
        print(f"Valid rows: {stats['valid_rows']}")
        print(f"Skipped rows: {stats['skipped_rows']}")
        
        if stats['skipped_rows'] > 0:
            print("\nWarning: Some rows will be skipped. Check the log for details.")
            
        proceed = input("\nDo you want to proceed with the actual import? (yes/no): ")
        if proceed.lower() != 'yes':
            print("\nImport cancelled.")
            return
    else:
        confirmation = input("Do you want to proceed? (yes/no): ")
        if confirmation.lower() != 'yes':
            print("\nImport cancelled.")
            return
    
    # Perform the actual import
    if not dry_run or proceed.lower() == 'yes':
        print("\nImporting data...")
        stats = import_temperature_data(csv_file_path, dry_run=False)
        
        print("\nImport completed successfully.")
        print(f"Total rows processed: {stats['total_rows']}")
        print(f"New records added: {stats['new_rows']}")
        print(f"Existing records updated: {stats['updated_rows']}")
        print(f"Records unchanged (same temperature): {stats['unchanged_rows']}")
        print(f"Rows skipped due to validation errors: {stats['skipped_rows']}")
        print(f"Rows with database errors: {stats['error_rows']}")

if __name__ == "__main__":
    main()
