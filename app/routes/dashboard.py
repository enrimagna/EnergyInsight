from flask import Blueprint, render_template, request
import json
import logging
import math
from datetime import datetime, timedelta, date
import calendar
from app.db.models import Database

logger = logging.getLogger(__name__)
bp = Blueprint('dashboard', __name__)

def get_date_range(time_range):
    """Calculate start and end dates based on time range selection."""
    today = datetime.now().date()
    end_date = today
    
    if time_range == 'ytd':
        # Year to date
        start_date = date(today.year, 1, 1)
    elif time_range == '7d':
        # Last 7 days
        start_date = today - timedelta(days=7)
    elif time_range == '30d':
        # Last 30 days
        start_date = today - timedelta(days=30)
    elif time_range == '90d':
        # Last 90 days
        start_date = today - timedelta(days=90)
    elif time_range == '1y':
        # Last year
        start_date = today - timedelta(days=365)
    elif time_range == '2y':
        # Last 2 years
        start_date = today - timedelta(days=365*2)
    elif time_range == '5y':
        # Last 5 years
        start_date = today - timedelta(days=365*5)
    elif time_range == 'custom':
        # Custom date range
        try:
            start_date_str = request.args.get('start_date')
            end_date_str = request.args.get('end_date')
            
            if not start_date_str or not end_date_str:
                # Default to last 30 days if no dates provided
                start_date = today - timedelta(days=30)
            else:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            # Invalid date format, default to last 30 days
            start_date = today - timedelta(days=30)
    else:
        # Default to last 7 days
        start_date = today - timedelta(days=7)
    
    return start_date, end_date

def aggregate_data(data, aggregation, date_key=0, avg_keys=None):
    """Aggregate data by day, week, month, quarter, or year.
    
    Args:
        data: List of data rows to aggregate
        aggregation: Aggregation method ('day', 'week', 'month', 'quarter', 'year')
        date_key: Index of the date field in each row
        avg_keys: List of indices for fields that should be averaged instead of summed
    """
    if not data or len(data) == 0:
        return []
    
    # Default avg_keys if not provided
    if avg_keys is None:
        avg_keys = []
    
    aggregated_data = {}
    # Track count of items per aggregation key for averaging
    counts = {}
    
    for item in data:
        # Get date from the data item
        if isinstance(item[date_key], str):
            date_obj = datetime.strptime(item[date_key], '%Y-%m-%d').date()
        elif isinstance(item[date_key], datetime):
            date_obj = item[date_key].date()
        else:
            date_obj = item[date_key]  # Assume it's already a date
        
        # Determine the aggregation key
        if aggregation == 'day':
            key = date_obj
        elif aggregation == 'week':
            # The start of the week (Monday)
            key = date_obj - timedelta(days=date_obj.weekday())
        elif aggregation == 'month':
            key = date(date_obj.year, date_obj.month, 1)
        elif aggregation == 'quarter':
            quarter = (date_obj.month - 1) // 3 + 1
            key = f"{date_obj.year}-Q{quarter}"
        elif aggregation == 'year':
            key = date_obj.year
        else:
            # Default to day if aggregation not recognized
            key = date_obj
        
        # Initialize the aggregation entry if not exists
        if key not in aggregated_data:
            # Copy all fields from the first item
            aggregated_data[key] = list(item)
            # Store the original date object for later formatting
            if aggregation != 'quarter':  # Quarter is already a string
                aggregated_data[key][date_key] = key
            # Initialize count for this key
            counts[key] = 1
        else:
            # Increment count for this key
            counts[key] += 1
            
            # Process each field
            for i in range(len(item)):
                if i != date_key and isinstance(item[i], (int, float)) and item[i] is not None:
                    if aggregated_data[key][i] is None:
                        aggregated_data[key][i] = 0
                    
                    # Sum the value
                    aggregated_data[key][i] += item[i]
    
    # Calculate averages for fields that should be averaged
    for key in aggregated_data:
        for i in avg_keys:
            if i < len(aggregated_data[key]) and aggregated_data[key][i] is not None and counts[key] > 0:
                # Convert sum to average
                aggregated_data[key][i] = aggregated_data[key][i] / counts[key]
    
    # Convert the dictionary back to a list
    result = list(aggregated_data.values())
    
    # Sort by date
    result.sort(key=lambda x: x[date_key])
    
    return result

def determine_aggregation(start_date, end_date):
    """Determine the appropriate data aggregation based on date range."""
    days_diff = (end_date - start_date).days
    
    logger.info(f"Determining aggregation for date range: {start_date} to {end_date} ({days_diff} days)")
    
    if days_diff <= 31:
        logger.info("Using 'day' aggregation (≤ 31 days)")
        return 'day'  # Show daily data for ranges ≤ 31 days
    elif days_diff <= 90:
        logger.info("Using 'week' aggregation (≤ 90 days)")
        return 'week'  # Show weekly data for ranges ≤ 90 days
    elif days_diff <= 365:
        logger.info("Using 'month' aggregation (≤ 365 days)")
        return 'month'  # Show monthly data for ranges ≤ 1 year
    elif days_diff <= 365 * 2:
        logger.info("Using 'quarter' aggregation (≤ 2 years)")
        return 'quarter'  # Show quarterly data for ranges ≤ 2 years
    else:
        logger.info("Using 'year' aggregation (> 2 years)")
        return 'year'  # Show yearly data for ranges > 2 years

@bp.route('/')
def index():
    """Main dashboard view showing energy and temperature data."""
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
    temp_data = db.get_temperature_data(start_date, end_date)
    
    # Debug: Log the data retrieved
    logger.info(f"Retrieved {len(energy_data) if energy_data else 0} energy data points")
    logger.info(f"Retrieved {len(temp_data) if temp_data else 0} temperature data points")
    
    # Aggregate data if needed
    logger.info(f"Using aggregation: {aggregation}")
    if aggregation != 'day':
        logger.info(f"Aggregating data with method: {aggregation}")
        # For energy data, COP (index 3) should be averaged
        energy_data = aggregate_data(energy_data, aggregation, avg_keys=[3])
        # For temperature data, temperature (index 1) should be averaged
        temp_data = aggregate_data(temp_data, aggregation, avg_keys=[1])
        logger.info(f"After aggregation: {len(energy_data) if energy_data else 0} energy data points, {len(temp_data) if temp_data else 0} temperature data points")
    
    # Create chart data
    charts = {}
    
    # Italian day and month names
    italian_days = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica']
    italian_months = ['Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno', 
                     'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre']
    
    # Log the first few data points to understand their structure
    if energy_data and len(energy_data) > 0:
        logger.info(f"First data point type: {type(energy_data[0])}")
        logger.info(f"First date type: {type(energy_data[0][0])}")
        logger.info(f"First date value: {energy_data[0][0]}")
        
        # If it's a string, try to parse it
        if isinstance(energy_data[0][0], str):
            logger.info(f"Date is a string: {energy_data[0][0]}")
            try:
                # Try to parse as date
                parsed_date = datetime.strptime(energy_data[0][0], '%Y-%m-%d').date()
                logger.info(f"Parsed date: {parsed_date}")
            except ValueError as e:
                logger.info(f"Could not parse date: {e}")
    
    # Energy chart
    if energy_data:
        timestamps = []
        consumed_values = []
        produced_values = []
        diesel_equivalent = []
        
        # Add temperature data to energy chart
        outdoor_temps = []
        temp_timestamps = []
        
        # Get temperature data for the same period
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
            # Log a few rows to see what's happening
            if i < 5:
                logger.info(f"Processing row {i}: {row}")
                logger.info(f"Date type: {type(row[0])}")
                if isinstance(row[0], str):
                    logger.info(f"Date string: {row[0]}")
                elif isinstance(row[0], date):
                    logger.info(f"Date object: {row[0]}")
                else:
                    logger.info(f"Unknown date type: {row[0]}")
            
            # Format date labels based on aggregation
            if isinstance(row[0], date):
                date_obj = row[0]
                if aggregation == 'day':
                    # Format as "Giorno della settimana, DD Mese"
                    day_of_week = italian_days[date_obj.weekday()]
                    month_name = italian_months[date_obj.month - 1]
                    formatted_date = f"{day_of_week}, {date_obj.day} {month_name}"
                    timestamps.append(formatted_date)
                    if i < 5:
                        logger.info(f"Formatted daily date: {formatted_date}")
                elif aggregation == 'week':
                    # Get ISO week number
                    year, week_num, _ = date_obj.isocalendar()
                    formatted_date = f"Settimana {week_num}, {year}"
                    timestamps.append(formatted_date)
                    if i < 5:
                        logger.info(f"Formatted weekly date: {formatted_date}")
                elif aggregation == 'month':
                    # Format as "Mese YYYY"
                    month_name = italian_months[date_obj.month - 1]
                    formatted_date = f"{month_name} {date_obj.year}"
                    timestamps.append(formatted_date)
                    if i < 5:
                        logger.info(f"Formatted monthly date: {formatted_date}")
                elif aggregation == 'year':
                    # Just show the year
                    formatted_date = f"Anno {date_obj.year}"
                    timestamps.append(formatted_date)
                    if i < 5:
                        logger.info(f"Formatted yearly date: {formatted_date}")
                else:
                    # Default format
                    formatted_date = date_obj.strftime('%Y-%m-%d')
                    timestamps.append(formatted_date)
                    if i < 5:
                        logger.info(f"Formatted default date: {formatted_date}")
            elif isinstance(row[0], str):
                if '-Q' in row[0]:
                    # Handle quarter format
                    parts = row[0].split('-Q')
                    if len(parts) == 2:
                        formatted_date = f"Trimestre {parts[1]} {parts[0]}"
                        timestamps.append(formatted_date)
                        if i < 5:
                            logger.info(f"Formatted quarterly date: {formatted_date}")
                    else:
                        timestamps.append(row[0])
                        if i < 5:
                            logger.info(f"Using original string date: {row[0]}")
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
                            if i < 5:
                                logger.info(f"Formatted daily date from string: {formatted_date}")
                        else:
                            # Use original string for other aggregations
                            timestamps.append(row[0])
                            if i < 5:
                                logger.info(f"Using original string date: {row[0]}")
                    except ValueError:
                        # If can't parse, use as is
                        timestamps.append(row[0])
                        if i < 5:
                            logger.info(f"Could not parse date string, using as is: {row[0]}")
            else:
                # Use as is if not a date object or string
                timestamps.append(str(row[0]))
                if i < 5:
                    logger.info(f"Using unknown date type as string: {str(row[0])}")
            
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
            
            # Debug temperature data
            logger.info(f"Temperature data points: {len(temp_data)}")
            if len(temp_data) > 0:
                logger.info(f"First temperature data point: {temp_data[0]}")
                logger.info(f"Temperature data structure: {[type(row) for row in temp_data[:3]]}")
            
            # Create a dictionary of temperature data by date for easy lookup
            temp_dict = {}
            for i, row in enumerate(temp_data):
                date_key = row[0]
                if isinstance(date_key, date):
                    temp_dict[date_key.strftime('%Y-%m-%d')] = outdoor_temps[i]
                else:
                    temp_dict[str(date_key)] = outdoor_temps[i]
            
            logger.info(f"Temperature dictionary keys: {list(temp_dict.keys())[:5]}")
            logger.info(f"Energy timestamps: {timestamps[:5]}")
            
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
            
            logger.info(f"Aligned temperatures: {aligned_temps[:5]}")
            logger.info(f"Number of aligned temperatures: {len(aligned_temps)}")
            logger.info(f"Number of non-None temperatures: {sum(1 for t in aligned_temps if t is not None)}")
            
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
                
                logger.info(f"Temperature range: min={min_temp}, max={max_temp}")
                
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
                
                logger.info(f"Dynamic temperature scale: min={min_temp}, max={max_temp}")
            else:
                # Fallback if no valid temperatures
                min_temp = -5
                max_temp = 35
                logger.warning("No valid temperatures found for scaling")
            
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
            
            logger.info(f"Added temperature data to energy chart with {len(aligned_temps)} points")
        
        charts['energy_chart'] = json.dumps(energy_chart)
        logger.info(f"Energy chart data created with {len(timestamps)} points")
    else:
        logger.warning("No energy data available to create chart")
    
    # Cost chart
    if energy_data:
        # Get current date for title
        current_date = datetime.now().date()
        
        # Prepare data for chart
        timestamps = []
        electricity_costs = []
        diesel_costs = []
        cop_values = []
        
        for row in energy_data:
            # Format date labels based on aggregation (same as above)
            if isinstance(row[0], date):
                date_obj = row[0]
                if aggregation == 'day':
                    # Format as "Giorno della settimana, DD Mese"
                    day_of_week = italian_days[date_obj.weekday()]
                    month_name = italian_months[date_obj.month - 1]
                    timestamps.append(f"{day_of_week}, {date_obj.day} {month_name}")
                elif aggregation == 'week':
                    # Get ISO week number
                    year, week_num, _ = date_obj.isocalendar()
                    timestamps.append(f"Settimana {week_num}, {year}")
                elif aggregation == 'month':
                    # Format as "Mese YYYY"
                    month_name = italian_months[date_obj.month - 1]
                    timestamps.append(f"{month_name} {date_obj.year}")
                elif aggregation == 'year':
                    # Just show the year
                    timestamps.append(f"Anno {date_obj.year}")
                else:
                    # Default format
                    timestamps.append(date_obj.strftime('%Y-%m-%d'))
            elif isinstance(row[0], str) and '-Q' in row[0]:
                # Handle quarter format
                parts = row[0].split('-Q')
                if len(parts) == 2:
                    timestamps.append(f"Trimestre {parts[1]} {parts[0]}")
                else:
                    timestamps.append(row[0])
            else:
                # Use as is if not a date object
                timestamps.append(str(row[0]))
            
            # Calculate costs
            electricity_cost = float(row[5] or 0)  # cost column
            electricity_costs.append(electricity_cost)
            
            # Get energy produced and COP
            energy_produced = float(row[2] or 0)  # Energy produced
            cop = float(row[3] or 3.5)  # COP value, default to 3.5 if None
            cop_values.append(cop)
            
            # Get prices for this month/year
            year = row[0].year if isinstance(row[0], date) else current_date.year
            month = row[0].month if isinstance(row[0], date) else current_date.month
            
            price_data = db.get_prices_for_month(year, month)
            
            if price_data:
                diesel_price = price_data['diesel_price']
                diesel_efficiency = price_data['diesel_efficiency']
            else:
                # Default values if no price data
                diesel_price = 1.50
                diesel_efficiency = 0.85
            
            # Calculate diesel cost using the formula from cost_calculations.md
            # Cost = (Produced / (DIESEL_EFFICIENCY * 10.5)) * DIESEL_PRICE
            if energy_produced > 0:
                diesel_cost = (energy_produced / (diesel_efficiency * 10.5)) * diesel_price
            else:
                diesel_cost = 0
            
            diesel_costs.append(diesel_cost)
        
        # Cumulative costs
        cum_electricity = [sum(electricity_costs[:i+1]) for i in range(len(electricity_costs))]
        cum_diesel = [sum(diesel_costs[:i+1]) for i in range(len(diesel_costs))]
        
        # Get period description for the chart title
        if time_range == 'ytd':
            period = f"Year to Date ({current_date.year})"
        elif time_range == '7d':
            period = "Last 7 Days"
        elif time_range == '30d':
            period = "Last 30 Days"
        elif time_range == '90d':
            period = "Last 90 Days"
        elif time_range == '1y':
            period = "Last Year"
        elif time_range == '2y':
            period = "Last 2 Years"
        elif time_range == '5y':
            period = "Last 5 Years"
        elif time_range == 'custom':
            period = f"{start_date} to {end_date}"
        else:
            period = "Selected Period"
        
        # Cost comparison chart
        cost_chart = {
            'type': 'line',
            'data': {
                'labels': timestamps,
                'datasets': [
                    {
                        'label': 'Heat Pump Cost (€)',
                        'data': cum_electricity,
                        'borderColor': 'rgb(54, 162, 235)',
                        'backgroundColor': 'rgba(54, 162, 235, 0.2)',
                        'tension': 0.1
                    },
                    {
                        'label': 'Diesel Cost (€)',
                        'data': cum_diesel,
                        'borderColor': 'rgb(255, 159, 64)',
                        'backgroundColor': 'rgba(255, 159, 64, 0.2)',
                        'tension': 0.1
                    }
                ]
            },
            'options': {
                'responsive': True,
                'interaction': {
                    'mode': 'index',
                    'intersect': False,
                },
                'scales': {
                    'y': {
                        'beginAtZero': True,
                        'title': {
                            'display': True,
                            'text': 'Cost (€)'
                        }
                    }
                },
                'plugins': {
                    'title': {
                        'display': True,
                        'text': f"Cumulative Cost Comparison - {period}"
                    },
                    'tooltip': {
                        'callbacks': {
                            'footer': 'function(tooltipItems) { return "Savings: €" + (tooltipItems[1].raw - tooltipItems[0].raw).toFixed(2); }'
                        }
                    }
                }
            }
        }
        charts['cost_chart'] = json.dumps(cost_chart)
        logger.info(f"Cost chart data created with {len(timestamps)} points")
    else:
        logger.warning("No cost data available to create chart")
    
    # Prepare context for the template
    context = {
        'charts': charts,
        'time_range': time_range,
        'energy_type': energy_type,
        'aggregation': aggregation,
        'start_date': start_date,
        'end_date': end_date
    }
    
    # Clean up
    db.close_connection()
    
    return render_template('dashboard/index.html', **context)
