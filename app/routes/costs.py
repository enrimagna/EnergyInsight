from flask import Blueprint, render_template, request
import json
import logging
from datetime import datetime, timedelta, date
import calendar
from app.db.models import Database
from app.routes.dashboard import get_date_range, determine_aggregation, aggregate_data

logger = logging.getLogger(__name__)
bp = Blueprint('costs', __name__)

@bp.route('/')
def index():
    """Cost analysis view showing cost comparison between heat pump and diesel."""
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
            # Format date labels based on aggregation
            formatted_date = ""
            if isinstance(row[0], date):
                date_obj = row[0]
                if aggregation == 'day':
                    # Format as "Giorno della settimana, DD Mese"
                    day_of_week = italian_days[date_obj.weekday()]
                    month_name = italian_months[date_obj.month - 1]
                    formatted_date = f"{day_of_week}, {date_obj.day} {month_name}"
                elif aggregation == 'week':
                    # Get ISO week number
                    year, week_num, _ = date_obj.isocalendar()
                    formatted_date = f"Settimana {week_num}, {year}"
                elif aggregation == 'month':
                    # Format as "Mese YYYY"
                    month_name = italian_months[date_obj.month - 1]
                    formatted_date = f"{month_name} {date_obj.year}"
                elif aggregation == 'year':
                    # Just show the year
                    formatted_date = f"Anno {date_obj.year}"
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
                        'text': f'Cost Comparison - {period}'
                    }
                }
            }
        }
        charts['cost_chart'] = json.dumps(cost_chart)
        logger.info(f"Cost chart data created with {len(timestamps)} points")
        
        # Calculate savings
        total_electricity_cost = sum(electricity_costs)
        total_diesel_cost = sum(diesel_costs)
        savings = total_diesel_cost - total_electricity_cost
        savings_percentage = (savings / total_diesel_cost * 100) if total_diesel_cost > 0 else 0
        
        # Add savings data to context
        charts['savings'] = {
            'electricity': round(total_electricity_cost, 2),
            'diesel': round(total_diesel_cost, 2),
            'amount': round(savings, 2),
            'percentage': round(savings_percentage, 2)
        }
    else:
        logger.warning("No energy data available to create cost chart")
    
    # Prepare context for the template
    context = {
        'charts': charts,
        'time_range': time_range,
        'energy_type': energy_type,
        'aggregation': aggregation,
        'start_date': start_date,
        'end_date': end_date,
        'active_page': 'costs'
    }
    
    # Clean up
    db.close_connection()
    
    return render_template('costs/index.html', **context)
