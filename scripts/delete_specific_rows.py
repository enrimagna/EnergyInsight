#!/usr/bin/env python3
"""
Script to delete specific rows (by ID range) from the energy_data table.
"""

import os
import logging
from dotenv import load_dotenv
from app.db.models import Database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def delete_rows_by_id_range(start_id, end_id, table_name="energy_data"):
    """Delete rows with IDs in the specified range from the given table."""
    # Load environment variables
    load_dotenv()
    
    # Get database connection
    db = Database()
    conn = db.get_connection()
    cursor = conn.cursor()
    
    try:
        # First, get the rows that will be deleted to show the user
        cursor.execute(f'''
        SELECT * FROM {table_name}
        WHERE id >= ? AND id <= ?
        ORDER BY id
        ''', (start_id, end_id))
        
        rows_to_delete = cursor.fetchall()
        
        if not rows_to_delete:
            logger.warning(f"No rows found with IDs between {start_id} and {end_id}")
            print(f"No rows found with IDs between {start_id} and {end_id}.")
            return
        
        # Display the rows that will be deleted
        print(f"\nThe following {len(rows_to_delete)} rows will be deleted:")
        print("-" * 80)
        print(f"{'ID':<6} {'Date':<12} {'Outdoor Temp':<15} {'Energy Consumed':<20}")
        print("-" * 80)
        
        for row in rows_to_delete:
            # Handle None values properly
            row_id = row['id'] if row['id'] is not None else 'N/A'
            date = row['date'] if row['date'] is not None else 'N/A'
            
            # Check if keys exist and handle None values
            outdoor_temp = 'N/A'
            if 'outdoor_temp' in row.keys() and row['outdoor_temp'] is not None:
                outdoor_temp = f"{row['outdoor_temp']}"
                
            energy_consumed = 'N/A'
            if 'total_energy_consumed' in row.keys() and row['total_energy_consumed'] is not None:
                energy_consumed = f"{row['total_energy_consumed']}"
                
            print(f"{row_id:<6} {date:<12} {outdoor_temp:<15} {energy_consumed:<20}")
        
        # Delete the rows
        cursor.execute(f'''
        DELETE FROM {table_name}
        WHERE id >= ? AND id <= ?
        ''', (start_id, end_id))
        
        # Commit the changes
        conn.commit()
        
        logger.info(f"Deleted {cursor.rowcount} rows from {table_name} table")
        print(f"\nSuccessfully deleted {cursor.rowcount} rows from the {table_name} table.")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting rows: {str(e)}")
        print(f"Error: {str(e)}")
        raise
    finally:
        # Close the database connection
        db.close_connection()

def main():
    """Main function to run the script."""
    start_id = 274
    end_id = 277
    table_name = "energy_data"
    
    logger.info(f"Starting deletion of rows with IDs from {start_id} to {end_id}...")
    
    # Confirm with user
    print(f"\nWARNING: This script will delete rows with IDs from {start_id} to {end_id}")
    print(f"from the {table_name} table.")
    print("This operation cannot be undone.\n")
    
    confirmation = input("Do you want to proceed? (yes/no): ")
    
    if confirmation.lower() == 'yes':
        delete_rows_by_id_range(start_id, end_id, table_name)
    else:
        print("\nDeletion cancelled.")

if __name__ == "__main__":
    main()
