#!/usr/bin/env python3
"""
Script to check if temperature_data table exists in the database.
"""

import os
import sqlite3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database path
db_path = os.getenv('DATABASE_PATH', 'app/db/energy_data.db')
print(f"Checking database at: {db_path}")

# Connect to the database
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check if temperature_data table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='temperature_data'")
result = cursor.fetchone()

if result:
    print("temperature_data table exists in the database")
    
    # Show table schema
    cursor.execute("PRAGMA table_info(temperature_data)")
    columns = cursor.fetchall()
    print("\nTable schema:")
    for col in columns:
        print(f"  {col['name']} ({col['type']})")
    
    # Count records
    cursor.execute("SELECT COUNT(*) FROM temperature_data")
    count = cursor.fetchone()[0]
    print(f"\nTable contains {count} records")
else:
    print("temperature_data table does NOT exist in the database")

# List all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("\nAll tables in database:")
for table in tables:
    print(f"  {table['name']}")

# Close connection
conn.close()
