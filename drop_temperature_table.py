#!/usr/bin/env python3
"""
Script to drop the temperature_data table from the database.
"""

import os
import sqlite3
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def drop_temperature_table():
    """Drop the temperature_data table from the database."""
    # Load environment variables
    load_dotenv()
    
    # Get database path
    db_path = os.getenv('DATABASE_PATH', 'app/db/energy_data.db')
    logger.info(f"Connecting to database at: {db_path}")
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Check if temperature_data table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='temperature_data'")
        result = cursor.fetchone()
        
        if result:
            logger.info("temperature_data table found, dropping it...")
            
            # Drop the table
            cursor.execute("DROP TABLE temperature_data")
            conn.commit()
            
            logger.info("temperature_data table successfully dropped")
        else:
            logger.info("temperature_data table does not exist, no action needed")
            
        # Verify the table is gone
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='temperature_data'")
        if not cursor.fetchone():
            logger.info("Verification successful: temperature_data table no longer exists")
        else:
            logger.error("Verification failed: temperature_data table still exists")
            
    except Exception as e:
        logger.error(f"Error dropping temperature_data table: {str(e)}")
        conn.rollback()
        raise
    finally:
        # Close connection
        conn.close()

if __name__ == "__main__":
    logger.info("Starting script to drop temperature_data table...")
    drop_temperature_table()
    logger.info("Script completed")
