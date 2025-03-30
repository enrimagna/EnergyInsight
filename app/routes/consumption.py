from flask import Blueprint, render_template, request
import json
import logging
from datetime import datetime, timedelta, date
import calendar
import math
from app.db.models import Database
from app.routes.dashboard import get_date_range, determine_aggregation, aggregate_data

logger = logging.getLogger(__name__)
bp = Blueprint('consumption', __name__)

@bp.route('/')
def index():
    """Energy consumption view showing energy usage data."""
    # Get time range from request
    time_range = request.args.get('time_range', default='7d')
    
    # Get energy type selection
    energy_type = request.args.get('energy_type', default='total')
    
    # Get date range
    start_date, end_date = get_date_range(time_range)
    
    # Check if auto aggregation is being used
    is_auto_aggregation = request.args.get('is_auto_aggregation') == 'true'
    logger.info(f"Is auto aggregation: {is_auto_aggregation}")
    
    # Determine aggregation level
    aggregation = request.args.get('aggregation', default='auto')
    logger.info(f"Requested aggregation from URL: {aggregation}")
    
    # Handle auto aggregation - always recalculate when auto is being used
    if aggregation == 'auto' or is_auto_aggregation:
        calculated_aggregation = determine_aggregation(start_date, end_date)
        logger.info(f"Auto-determined aggregation: {calculated_aggregation}")
        aggregation = calculated_aggregation
    
    # Get data from database
    db = Database()
    energy_data = db.get_energy_data(start_date, end_date, energy_type)
    
    # Debug: Log the data retrieved
    logger.info(f"Retrieved {len(energy_data) if energy_data else 0} energy data points")
    
    # Aggregate data if needed
    logger.info(f"Using aggregation: {aggregation}")
    if aggregation != 'day':
        logger.info(f"Aggregating data with method: {aggregation}")
        # For energy data, COP (index 3) should be averaged
        energy_data = aggregate_data(energy_data, aggregation, avg_keys=[3])
        logger.info(f"After aggregation: {len(energy_data) if energy_data else 0} energy data points")
    
    # Create chart data
    charts = {}
    
    # Italian day and month names
    italian_days = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica']
    italian_months = ['Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno', 
                     'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre']
    
    # Energy chart
    if energy_data:
        timestamps = []
        consumed_values = []
        produced_values = []
        
        # Add temperature data to energy chart
        outdoor_temps = []
        temp_timestamps = []
        
        # Get temperature data for the same period
        temp_data = db.get_temperature_data(start_date, end_date)
        if temp_data:
            for row in temp_data:
                if isinstance(row[0], date):
                    temp_timestamps.append(row[0])
                elif isinstance(row[0], str):
                    try:
                        temp_date = datetime.strptime(row[0], '%Y-%m-%d').date()
                        temp_timestamps.append(temp_date)
                    except ValueError:
                        temp_timestamps.append(row[0])
                else:
                    temp_timestamps.append(str(row[0]))
                
                # Temperature values
                outdoor_temps.append(float(row[1] or 0))
        
        current_date = datetime.now().date()
        
        # Prepare data for chart
        for i, row in enumerate(energy_data):
            # Format date labels based on aggregation
            if isinstance(row[0], date):
                date_obj = row[0]
                if aggregation == 'day':
                    # Format as "Giorno della settimana, DD Mese"
                    day_of_week = italian_days[date_obj.weekday()]
                    month_name = italian_months[date_obj.month - 1]
                    formatted_date = f"{day_of_week}, {date_obj.day} {month_name}"
                    timestamps.append(formatted_date)
                elif aggregation == 'week':
                    # Get ISO week number
                    year, week_num, _ = date_obj.isocalendar()
                    formatted_date = f"Settimana {week_num}, {year}"
                    timestamps.append(formatted_date)
                elif aggregation == 'month':
                    # Format as "Mese YYYY"
                    month_name = italian_months[date_obj.month - 1]
                    formatted_date = f"{month_name} {date_obj.year}"
                    timestamps.append(formatted_date)
                elif aggregation == 'year':
                    # Just show the year
                    formatted_date = f"Anno {date_obj.year}"
                    timestamps.append(formatted_date)
                else:
                    # Default format
                    formatted_date = date_obj.strftime('%Y-%m-%d')
                    timestamps.append(formatted_date)
            elif isinstance(row[0], str):
                if '-Q' in row[0]:
                    # Handle quarter format
                    parts = row[0].split('-Q')
                    if len(parts) == 2:
                        formatted_date = f"Trimestre {parts[1]} {parts[0]}"
                        timestamps.append(formatted_date)
                    else:
                        timestamps.append(row[0])
                else:
                    # Try to parse the date string
                    try:
                        date_obj = datetime.strptime(row[0], '%Y-%m-%d').date()
                        if aggregation == 'day':
                            # Format as "Giorno della settimana, DD Mese"
                            day_of_week = italian_days[date_obj.weekday()]
                            month_name = italian_months[date_obj.month - 1]
                            formatted_date = f"{day_of_week}, {date_obj.day} {month_name}"
                            timestamps.append(formatted_date)
                        else:
                            # Use original string for other aggregations
                            timestamps.append(row[0])
                    except ValueError:
                        # If can't parse, use as is
                        timestamps.append(row[0])
            else:
                # Use as is if not a date object or string
                timestamps.append(str(row[0]))
            
            # Energy values
            consumed_values.append(float(row[1] or 0))  # Consumption
            produced_values.append(float(row[2] or 0))  # Production
        
        # Create energy chart configuration
        energy_chart = {
            'type': 'bar',
            'data': {
                'labels': timestamps,
                'datasets': [
                    {
                        'label': f'{energy_type.capitalize()} Energy Consumed (kWh)',
                        'data': consumed_values,
                        'backgroundColor': 'rgba(255, 99, 132, 0.5)',
                        'borderColor': 'rgb(255, 99, 132)',
                        'borderWidth': 1,
                        'yAxisID': 'y'
                    },
                    {
                        'label': f'{energy_type.capitalize()} Energy Produced (kWh)',
                        'data': produced_values,
                        'backgroundColor': 'rgba(75, 192, 192, 0.5)',
                        'borderColor': 'rgb(75, 192, 192)',
                        'borderWidth': 1,
                        'yAxisID': 'y'
                    }
                ]
            },
            'options': {
                'responsive': True,
                'scales': {
                    'y': {
                        'beginAtZero': True,
                        'title': {
                            'display': True,
                            'text': 'Energy (kWh)'
                        },
                        'position': 'left'
                    }
                },
                'plugins': {
                    'title': {
                        'display': True,
                        'text': f'{energy_type.capitalize()} Energy (kWh)'
                    }
                }
            }
        }
        
        # Add temperature data to energy chart if available
        if temp_data:
            # Map temperature data to energy data timestamps
            aligned_temps = []
            
            # Create a dictionary of temperature data by date for easy lookup
            temp_dict = {}
            for i, date_val in enumerate(temp_timestamps):
                if isinstance(date_val, date):
                    temp_dict[date_val.strftime('%Y-%m-%d')] = outdoor_temps[i]
                else:
                    temp_dict[str(date_val)] = outdoor_temps[i]
            
            # For each energy timestamp, find the corresponding temperature
            for i, date_val in enumerate(timestamps):
                # Try to extract date from formatted string
                original_date = None
                if i < len(energy_data):
                    original_date = energy_data[i][0]
                    if isinstance(original_date, date):
                        date_key = original_date.strftime('%Y-%m-%d')
                        if date_key in temp_dict:
                            aligned_temps.append(temp_dict[date_key])
                            continue
                
                # If we couldn't match with original date, try direct match
                if date_val in temp_dict:
                    aligned_temps.append(temp_dict[date_val])
                else:
                    # If still no match, log and use None
                    if i < 5:  # Only log first few to avoid spam
                        logger.info(f"No temperature match for date: {date_val}, original: {original_date}")
                    aligned_temps.append(None)
            
            # If we have no aligned temperatures, use the original temperature data
            if sum(1 for t in aligned_temps if t is not None) == 0:
                logger.warning("No temperature data could be aligned with energy data. Using original temperature data.")
                # Use the original temperature data directly
                aligned_temps = outdoor_temps
                
                # If timestamps don't match in length, adjust
                if len(aligned_temps) > len(timestamps):
                    aligned_temps = aligned_temps[:len(timestamps)]
                elif len(aligned_temps) < len(timestamps):
                    # Pad with None
                    aligned_temps.extend([None] * (len(timestamps) - len(aligned_temps)))
            
            # Calculate dynamic min/max for temperature scale
            # Filter out None values
            valid_temps = [t for t in aligned_temps if t is not None]
            if valid_temps:
                min_temp = min(valid_temps)
                max_temp = max(valid_temps)
                
                # Add padding to make the visualization better
                temp_range = max_temp - min_temp
                if temp_range < 10:  # If range is small, add more padding
                    min_temp = min_temp - 5
                    max_temp = max_temp + 5
                else:
                    # Add 10% padding on each side
                    padding = temp_range * 0.1
                    min_temp = min_temp - padding
                    max_temp = max_temp + padding
                
                # Round to nearest 5
                min_temp = math.floor(min_temp / 5) * 5
                max_temp = math.ceil(max_temp / 5) * 5
            else:
                # Fallback if no valid temperatures
                min_temp = -5
                max_temp = 35
            
            # Add temperature dataset to the energy chart
            energy_chart['data']['datasets'].append({
                'label': 'Outdoor Temperature (°C)',
                'data': aligned_temps,
                'backgroundColor': 'rgba(54, 162, 235, 0)',
                'borderColor': 'rgb(54, 162, 235)',
                'borderWidth': 2,
                'type': 'line',
                'yAxisID': 'y1',
                'tension': 0.1,
                'pointRadius': 3,
                'fill': False,
                'order': 0  # Make sure temperature is drawn on top
            })
            
            # Add secondary y-axis for temperature
            energy_chart['options']['scales']['y1'] = {
                'type': 'linear',
                'display': True,
                'position': 'right',
                'title': {
                    'display': True,
                    'text': 'Temperature (°C)'
                },
                'grid': {
                    'drawOnChartArea': False  # only want the grid lines for y1 axis, not y
                },
                # Dynamic min and max based on actual data
                'min': min_temp,
                'max': max_temp,
                'ticks': {
                    'stepSize': (max_temp - min_temp) / 5  # Dynamic step size
                }
            }
            
            # Update chart title to indicate both metrics
            energy_chart['options']['plugins']['title']['text'] = f'{energy_type.capitalize()} Energy & Temperature'
        
        charts['energy_chart'] = json.dumps(energy_chart)
        logger.info(f"Energy chart data created with {len(timestamps)} points")
    else:
        logger.warning("No energy data available to create chart")
    
    # Prepare context for the template
    context = {
        'charts': charts,
        'time_range': time_range,
        'energy_type': energy_type,
        'aggregation': aggregation,
        'start_date': start_date,
        'end_date': end_date,
        'active_page': 'consumption'
    }
    
    # Clean up
    db.close_connection()
    
    return render_template('consumption/index.html', **context)
