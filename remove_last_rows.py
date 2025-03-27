#!/usr/bin/env python3
"""
Utility script to remove the last N rows from the energy_data table
"""
import sqlite3
import os
import argparse
from dotenv import load_dotenv

def main():
    """Main function to remove rows"""
    parser = argparse.ArgumentParser(description="Remove the last N rows from the energy_data table")
    parser.add_argument("--rows", type=int, default=3, help="Number of rows to remove")
    parser.add_argument("--table", type=str, default="energy_data", 
                       choices=["energy_data", "temperature_data", "prices"], 
                       help="Table to remove rows from")
    args = parser.parse_args()
    
    # Load database path from .env file
    load_dotenv()
    db_path = os.getenv('DATABASE_PATH', 'app/db/energy_data.db')
    
    print(f"Connecting to database at {db_path}")
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get the last N rows
    cursor.execute(f"SELECT * FROM {args.table} ORDER BY id DESC LIMIT ?", (args.rows,))
    rows_to_delete = cursor.fetchall()
    
    if not rows_to_delete:
        print(f"No rows found in table {args.table}")
        return
    
    print(f"Found {len(rows_to_delete)} rows to delete from {args.table}:")
    for row in rows_to_delete:
        if args.table == "energy_data":
            print(f"  ID: {row['id']}, Date: {row['date']}, Heating consumed: {row['heating_energy_consumed']}, Hot water consumed: {row['hot_water_energy_consumed']}")
        elif args.table == "temperature_data":
            print(f"  ID: {row['id']}, Date: {row['date']}, Indoor temp: {row['indoor_temp']}, Outdoor temp: {row['outdoor_temp']}")
        else:
            print(f"  ID: {row['id']}, Date: {row['date']}")
    
    # Confirm deletion
    confirm = input(f"Are you sure you want to delete these {len(rows_to_delete)} rows? (y/n): ")
    
    if confirm.lower() == 'y':
        # Delete the rows
        ids_to_delete = [row['id'] for row in rows_to_delete]
        placeholders = ', '.join('?' for _ in ids_to_delete)
        cursor.execute(f"DELETE FROM {args.table} WHERE id IN ({placeholders})", ids_to_delete)
        conn.commit()
        
        print(f"Deleted {cursor.rowcount} rows from {args.table}")
    else:
        print("Operation cancelled")
    
    conn.close()

if __name__ == "__main__":
    main()
