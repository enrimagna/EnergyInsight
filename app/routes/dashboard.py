from flask import Blueprint, render_template, request
import json
import logging
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

def aggregate_data(data, aggregation, date_key=0):
    """Aggregate data by day, week, month, quarter, or year."""
    if not data or len(data) == 0:
        return []
    
    aggregated_data = {}
    
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
        else:
            # Sum numeric values (skip the date field)
            for i in range(len(item)):
                if i != date_key and isinstance(item[i], (int, float)) and item[i] is not None:
                    if aggregated_data[key][i] is None:
                        aggregated_data[key][i] = 0
                    aggregated_data[key][i] += item[i]
    
    # Convert the dictionary back to a list
    result = list(aggregated_data.values())
    
    # Format date labels for display
    for item in result:
        if aggregation == 'day':
            item[date_key] = item[date_key].strftime('%Y-%m-%d')
        elif aggregation == 'week':
            end_of_week = item[date_key] + timedelta(days=6)
            item[date_key] = f"{item[date_key].strftime('%Y-%m-%d')} to {end_of_week.strftime('%Y-%m-%d')}"
        elif aggregation == 'month':
            item[date_key] = item[date_key].strftime('%Y-%m')
        elif aggregation == 'quarter':
            # Already formatted as YYYY-QN
            pass
        elif aggregation == 'year':
            item[date_key] = str(item[date_key])
    
    # Sort by date
    result.sort(key=lambda x: x[date_key])
    
    return result

def determine_aggregation(start_date, end_date):
    """Determine the appropriate data aggregation based on date range."""
    days_diff = (end_date - start_date).days
    
    if days_diff <= 31:
        return 'day'  # Show daily data for ranges <= 31 days
    elif days_diff <= 90:
        return 'week'  # Show weekly data for ranges <= 90 days
    elif days_diff <= 365:
        return 'month'  # Show monthly data for ranges <= 1 year
    elif days_diff <= 365 * 2:
        return 'quarter'  # Show quarterly data for ranges <= 2 years
    else:
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
    
    # Determine aggregation level
    aggregation = request.args.get('aggregation')
    if not aggregation:
        aggregation = determine_aggregation(start_date, end_date)
    
    # Get data from database
    db = Database()
    energy_data = db.get_energy_data(start_date, end_date, energy_type)
    temp_data = db.get_temperature_data(start_date, end_date)
    
    # Debug: Log the data retrieved
    logger.info(f"Retrieved {len(energy_data) if energy_data else 0} energy data points")
    logger.info(f"Retrieved {len(temp_data) if temp_data else 0} temperature data points")
    
    # Aggregate data if needed
    if aggregation != 'day':
        energy_data = aggregate_data(energy_data, aggregation)
        temp_data = aggregate_data(temp_data, aggregation)
    
    # Create chart data
    charts = {}
    
    # Energy consumption & production chart
    if energy_data:
        # Prepare data for chart
        timestamps = []
        consumed_values = []
        produced_values = []
        
        for row in energy_data:
            # Format date
            if isinstance(row[0], str):
                timestamps.append(row[0])
            else:
                timestamps.append(row[0].strftime('%Y-%m-%d'))
            
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
                        }
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
            # Format date
            if isinstance(row[0], str):
                timestamps.append(row[0])
                date_obj = datetime.strptime(row[0], '%Y-%m-%d').date()
            else:
                timestamps.append(row[0].strftime('%Y-%m-%d'))
                date_obj = row[0]
            
            # Calculate costs
            electricity_cost = float(row[5] or 0)  # cost column
            electricity_costs.append(electricity_cost)
            
            # Get energy produced and COP
            energy_produced = float(row[2] or 0)  # Energy produced
            cop = float(row[3] or 3.5)  # COP value, default to 3.5 if None
            cop_values.append(cop)
            
            # Get prices for this month/year
            year = date_obj.year if isinstance(date_obj, date) else current_date.year
            month = date_obj.month if isinstance(date_obj, date) else current_date.month
            
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
        
        # COP chart
        cop_chart = {
            'type': 'line',
            'data': {
                'labels': timestamps,
                'datasets': [
                    {
                        'label': 'COP (Coefficient of Performance)',
                        'data': cop_values,
                        'borderColor': 'rgb(54, 162, 235)',
                        'backgroundColor': 'rgba(54, 162, 235, 0.2)',
                        'tension': 0.1,
                        'fill': False
                    }
                ]
            },
            'options': {
                'responsive': True,
                'scales': {
                    'y': {
                        'beginAtZero': False,
                        'title': {
                            'display': True,
                            'text': 'COP'
                        }
                    }
                },
                'plugins': {
                    'title': {
                        'display': True,
                        'text': f'Heat Pump Efficiency (COP) - {period}'
                    }
                }
            }
        }
        charts['cop_chart'] = json.dumps(cop_chart)
        
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
    
    # Temperature chart
    if temp_data:
        # Prepare data for chart
        timestamps = []
        indoor_temps = []
        outdoor_temps = []
        
        for row in temp_data:
            # Format date
            if isinstance(row[0], str):
                timestamps.append(row[0])
            else:
                timestamps.append(row[0].strftime('%Y-%m-%d'))
            
            # Temperature values
            indoor_temps.append(float(row[1]))
            outdoor_temps.append(float(row[2]))
        
        temp_chart = {
            'type': 'line',
            'data': {
                'labels': timestamps,
                'datasets': [
                    {
                        'label': 'Indoor Temperature (°C)',
                        'data': indoor_temps,
                        'borderColor': 'rgb(255, 99, 132)',
                        'backgroundColor': 'rgba(255, 99, 132, 0.2)',
                        'tension': 0.1
                    },
                    {
                        'label': 'Outdoor Temperature (°C)',
                        'data': outdoor_temps,
                        'borderColor': 'rgb(54, 162, 235)',
                        'backgroundColor': 'rgba(54, 162, 235, 0.2)',
                        'tension': 0.1
                    }
                ]
            },
            'options': {
                'responsive': True,
                'scales': {
                    'y': {
                        'title': {
                            'display': True,
                            'text': 'Temperature (°C)'
                        }
                    }
                },
                'plugins': {
                    'title': {
                        'display': True,
                        'text': 'Temperature Trends'
                    }
                }
            }
        }
        charts['temp_chart'] = json.dumps(temp_chart)
        logger.info(f"Temperature chart data created with {len(timestamps)} points")
    else:
        logger.warning("No temperature data available to create chart")
    
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
