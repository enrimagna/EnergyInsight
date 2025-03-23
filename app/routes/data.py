from flask import Blueprint, jsonify, request
from app.db.models import Database
from datetime import datetime, timedelta

bp = Blueprint('data', __name__)

# Exempt API endpoints from CSRF protection
@bp.route('/energy', methods=['GET'])
def get_energy_data():
    """API endpoint for energy consumption data."""
    days = request.args.get('days', default=7, type=int)
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Get data from database
    db = Database()
    energy_data = db.get_energy_data(start_date, end_date)
    
    # Format data for API response
    result = []
    for row in energy_data:
        result.append({
            'timestamp': row[0].isoformat(),
            'power_consumption': row[1],
            'energy_consumed': row[2],
            'cost': row[3]
        })
    
    return jsonify(result)

@bp.route('/temperature', methods=['GET'])
def get_temperature_data():
    """API endpoint for temperature data."""
    days = request.args.get('days', default=7, type=int)
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Get data from database
    db = Database()
    temp_data = db.get_temperature_data(start_date, end_date)
    
    # Format data for API response
    result = []
    for row in temp_data:
        result.append({
            'timestamp': row[0].isoformat(),
            'indoor_temp': row[1],
            'outdoor_temp': row[2]
        })
    
    return jsonify(result)

@bp.route('/prices', methods=['GET'])
def get_prices():
    """API endpoint for current energy prices."""
    import os
    from dotenv import load_dotenv
    
    # Load current prices from .env
    load_dotenv()
    
    prices = {
        'electricity': float(os.getenv('ELECTRICITY_PRICE', '0.28')),
        'diesel': float(os.getenv('DIESEL_PRICE', '1.50')),
        'diesel_efficiency': float(os.getenv('DIESEL_EFFICIENCY', '0.85'))
    }
    
    return jsonify(prices)
