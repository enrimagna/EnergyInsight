from flask import Blueprint, render_template, request
import plotly.graph_objects as go
import json
import logging
from datetime import datetime, timedelta, date
from app.db.models import Database
from app.routes.dashboard import get_date_range, determine_aggregation, aggregate_data

logger = logging.getLogger(__name__)
bp = Blueprint('temperature', __name__)

@bp.route('/')
def index():
    """Temperature data view showing temperature trends and COP."""
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
    temp_data = db.get_temperature_data(start_date, end_date)
    
    # Get energy data for COP
    energy_data = db.get_energy_data(start_date, end_date, energy_type)
    
    # Debug: Log the data retrieved
    logger.info(f"Retrieved {len(temp_data) if temp_data else 0} temperature data points")
    logger.info(f"Retrieved {len(energy_data) if energy_data else 0} energy data points")
    
    # Aggregate data if needed
    logger.info(f"Using aggregation: {aggregation}")
    if aggregation != 'day':
        logger.info(f"Aggregating data with method: {aggregation}")
        # For temperature data, temperature (index 1) should be averaged
        temp_data = aggregate_data(temp_data, aggregation, avg_keys=[1])
        # For energy data, COP (index 3) should be averaged
        energy_data = aggregate_data(energy_data, aggregation, avg_keys=[3])
        logger.info(f"After aggregation: {len(temp_data) if temp_data else 0} temperature data points, {len(energy_data) if energy_data else 0} energy data points")
    
    # Create graphs
    charts = {}
    
    # Italian day and month names
    italian_days = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica']
    italian_months = ['Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno', 
                     'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre']
    
    # Get period description for the chart title
    current_date = datetime.now().date()
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
    
    # Combined temperature and COP graph
    if temp_data and energy_data:
        # Process temperature data
        temp_timestamps = []
        outdoor_temps = []
        
        for row in temp_data:
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
                temp_timestamps.append(formatted_date)
            elif isinstance(row[0], str):
                if '-Q' in row[0]:
                    # Handle quarter format
                    parts = row[0].split('-Q')
                    if len(parts) == 2:
                        formatted_date = f"Trimestre {parts[1]} {parts[0]}"
                        temp_timestamps.append(formatted_date)
                    else:
                        temp_timestamps.append(row[0])
                else:
                    # Try to parse the date string
                    try:
                        date_obj = datetime.strptime(row[0], '%Y-%m-%d').date()
                        if aggregation == 'day':
                            # Format as "Giorno della settimana, DD Mese"
                            day_of_week = italian_days[date_obj.weekday()]
                            month_name = italian_months[date_obj.month - 1]
                            formatted_date = f"{day_of_week}, {date_obj.day} {month_name}"
                            temp_timestamps.append(formatted_date)
                        else:
                            # Use original string for other aggregations
                            temp_timestamps.append(row[0])
                    except ValueError:
                        # If can't parse, use as is
                        temp_timestamps.append(row[0])
            else:
                # Use as is if not a date object or string
                temp_timestamps.append(str(row[0]))
            
            # Temperature values - only outdoor temperature is available now
            outdoor_temps.append(float(row[1] or 0))
        
        # Process COP data
        cop_timestamps = []
        cop_values = []
        
        for row in energy_data:
            # Format date labels based on aggregation (same as above)
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
                cop_timestamps.append(formatted_date)
            elif isinstance(row[0], str):
                if '-Q' in row[0]:
                    # Handle quarter format
                    parts = row[0].split('-Q')
                    if len(parts) == 2:
                        formatted_date = f"Trimestre {parts[1]} {parts[0]}"
                        cop_timestamps.append(formatted_date)
                    else:
                        cop_timestamps.append(row[0])
                else:
                    # Try to parse the date string
                    try:
                        date_obj = datetime.strptime(row[0], '%Y-%m-%d').date()
                        if aggregation == 'day':
                            # Format as "Giorno della settimana, DD Mese"
                            day_of_week = italian_days[date_obj.weekday()]
                            month_name = italian_months[date_obj.month - 1]
                            formatted_date = f"{day_of_week}, {date_obj.day} {month_name}"
                            cop_timestamps.append(formatted_date)
                        else:
                            # Use original string for other aggregations
                            cop_timestamps.append(row[0])
                    except ValueError:
                        # If can't parse, use as is
                        cop_timestamps.append(row[0])
            else:
                # Use as is if not a date object or string
                cop_timestamps.append(str(row[0]))
            
            # COP values
            cop = float(row[3] or 3.5)  # COP value, default to 3.5 if None
            cop_values.append(cop)
        
        # Create combined chart with dual Y-axes
        combined_chart = {
            'type': 'line',
            'data': {
                'labels': temp_timestamps,  # Use temperature timestamps as the base
                'datasets': [
                    {
                        'label': 'Temperatura Esterna (°C)',
                        'data': outdoor_temps,
                        'borderColor': 'rgb(54, 162, 235)',
                        'backgroundColor': 'rgba(54, 162, 235, 0.2)',
                        'tension': 0.1,
                        'yAxisID': 'y'
                    },
                    {
                        'label': 'COP (Coefficiente di Prestazione)',
                        'data': cop_values,
                        'borderColor': 'rgb(255, 99, 132)',
                        'backgroundColor': 'rgba(255, 99, 132, 0.2)',
                        'tension': 0.1,
                        'yAxisID': 'y1'
                    }
                ]
            },
            'options': {
                'responsive': True,
                'interaction': {
                    'mode': 'index',
                    'intersect': False
                },
                'scales': {
                    'y': {
                        'type': 'linear',
                        'display': True,
                        'position': 'left',
                        'title': {
                            'display': True,
                            'text': 'Temperatura (°C)'
                        }
                    },
                    'y1': {
                        'type': 'linear',
                        'display': True,
                        'position': 'right',
                        'title': {
                            'display': True,
                            'text': 'COP'
                        },
                        'grid': {
                            'drawOnChartArea': False
                        }
                    }
                },
                'plugins': {
                    'title': {
                        'display': True,
                        'text': f'Temperatura e Efficienza (COP) - {period}'
                    },
                    'tooltip': {
                        'mode': 'index',
                        'intersect': False
                    }
                }
            }
        }
        
        charts['combined_chart'] = json.dumps(combined_chart)
        logger.info(f"Combined chart data created with {len(temp_timestamps)} points")
    else:
        logger.warning("Insufficient data to create combined chart")
        
        # Create individual charts if we have at least one type of data
        if temp_data:
            # Process temperature data and create temperature chart
            temp_timestamps = []
            outdoor_temps = []
            
            for row in temp_data:
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
                    temp_timestamps.append(formatted_date)
                elif isinstance(row[0], str):
                    if '-Q' in row[0]:
                        # Handle quarter format
                        parts = row[0].split('-Q')
                        if len(parts) == 2:
                            formatted_date = f"Trimestre {parts[1]} {parts[0]}"
                            temp_timestamps.append(formatted_date)
                        else:
                            temp_timestamps.append(row[0])
                    else:
                        # Try to parse the date string
                        try:
                            date_obj = datetime.strptime(row[0], '%Y-%m-%d').date()
                            if aggregation == 'day':
                                # Format as "Giorno della settimana, DD Mese"
                                day_of_week = italian_days[date_obj.weekday()]
                                month_name = italian_months[date_obj.month - 1]
                                formatted_date = f"{day_of_week}, {date_obj.day} {month_name}"
                                temp_timestamps.append(formatted_date)
                            else:
                                # Use original string for other aggregations
                                temp_timestamps.append(row[0])
                        except ValueError:
                            # If can't parse, use as is
                            temp_timestamps.append(row[0])
                else:
                    # Use as is if not a date object or string
                    temp_timestamps.append(str(row[0]))
                
                # Temperature values - only outdoor temperature is available now
                outdoor_temps.append(float(row[1] or 0))
            
            temp_chart = {
                'type': 'line',
                'data': {
                    'labels': temp_timestamps,
                    'datasets': [
                        {
                            'label': 'Temperatura Esterna (°C)',
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
                                'text': 'Temperatura (°C)'
                            }
                        }
                    },
                    'plugins': {
                        'title': {
                            'display': True,
                            'text': 'Andamento Temperature Esterne'
                        }
                    }
                }
            }
            charts['temp_chart'] = json.dumps(temp_chart)
            logger.info(f"Temperature chart data created with {len(temp_timestamps)} points")
        
        if energy_data:
            # Process COP data and create COP chart
            cop_timestamps = []
            cop_values = []
            
            for row in energy_data:
                # Format date labels based on aggregation (same as above)
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
                    cop_timestamps.append(formatted_date)
                elif isinstance(row[0], str):
                    if '-Q' in row[0]:
                        # Handle quarter format
                        parts = row[0].split('-Q')
                        if len(parts) == 2:
                            formatted_date = f"Trimestre {parts[1]} {parts[0]}"
                            cop_timestamps.append(formatted_date)
                        else:
                            cop_timestamps.append(row[0])
                    else:
                        # Try to parse the date string
                        try:
                            date_obj = datetime.strptime(row[0], '%Y-%m-%d').date()
                            if aggregation == 'day':
                                # Format as "Giorno della settimana, DD Mese"
                                day_of_week = italian_days[date_obj.weekday()]
                                month_name = italian_months[date_obj.month - 1]
                                formatted_date = f"{day_of_week}, {date_obj.day} {month_name}"
                                cop_timestamps.append(formatted_date)
                            else:
                                # Use original string for other aggregations
                                cop_timestamps.append(row[0])
                        except ValueError:
                            # If can't parse, use as is
                            cop_timestamps.append(row[0])
                else:
                    # Use as is if not a date object or string
                    cop_timestamps.append(str(row[0]))
                
                # COP values
                cop = float(row[3] or 3.5)  # COP value, default to 3.5 if None
                cop_values.append(cop)
            
            cop_chart = {
                'type': 'line',
                'data': {
                    'labels': cop_timestamps,
                    'datasets': [
                        {
                            'label': 'COP (Coefficiente di Prestazione)',
                            'data': cop_values,
                            'borderColor': 'rgb(255, 99, 132)',
                            'backgroundColor': 'rgba(255, 99, 132, 0.2)',
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
                            'text': f'Efficienza Pompa di Calore (COP) - {period}'
                        }
                    }
                }
            }
            charts['cop_chart'] = json.dumps(cop_chart)
            logger.info(f"COP chart data created with {len(cop_timestamps)} points")
    
    # Prepare context for the template
    context = {
        'charts': charts,
        'time_range': time_range,
        'energy_type': energy_type,
        'aggregation': aggregation,
        'start_date': start_date,
        'end_date': end_date,
        'active_page': 'temperature'
    }
    
    # Clean up
    db.close_connection()
    
    return render_template('temperature/index.html', **context)

@bp.route('/edit', methods=('GET', 'POST'))
def edit():
    """Settings page for editing temperature data."""
    # Get database connection
    db = Database()
    
    if request.method == 'POST':
        logger.info(f"Form data keys: {list(request.form.keys())}")
        
        # Handle editing a specific temperature row
        if 'update_temp_row' in request.form:
            temp_id = request.form.get('temp_id', '')
            temp_date = request.form.get('temp_date', '')
            outdoor_temp = request.form.get('outdoor_temp', '')
            
            # Log the received values for debugging
            logger.info(f"Received temperature row update request - ID: {temp_id}, Date: {temp_date}, "
                        f"Outdoor Temperature: {outdoor_temp}")
            
            # Validate inputs
            errors = False
            if not temp_date or not outdoor_temp:
                flash('All fields are required', 'danger')
                errors = True
            else:
                try:
                    # Convert date string to date object
                    date_obj = datetime.strptime(temp_date, '%Y-%m-%d').date()
                    outdoor_temp = float(outdoor_temp)
                    
                    # Log the converted values
                    logger.info(f"Converted values - Date: {date_obj}, Outdoor Temp: {outdoor_temp}")
                    
                    if outdoor_temp < -50 or outdoor_temp > 60:  # Reasonable temperature range
                        flash('Invalid temperature value', 'danger')
                        errors = True
                except ValueError:
                    flash('Invalid date or temperature value', 'danger')
                    errors = True
            
            if not errors:
                try:
                    # Update the database with the new temperature value
                    result = db.add_temperature_data(
                        timestamp=date_obj,
                        outdoor_temp=outdoor_temp
                    )
                    
                    if result:
                        flash(f'Temperatura per {temp_date} aggiornata con successo', 'success')
                    else:
                        flash('Errore durante l\'aggiornamento della temperatura', 'danger')
                except Exception as e:
                    logger.error(f"Error updating temperature row: {str(e)}")
                    flash(f'Errore durante l\'aggiornamento della temperatura: {str(e)}', 'danger')
    
    # Get temperature data for display
    # Default to current year and month
    current_date = datetime.now()
    selected_year = request.args.get('year', str(current_date.year))
    selected_month = request.args.get('month', str(current_date.month))
    
    try:
        selected_year = int(selected_year)
        selected_month = int(selected_month)
    except ValueError:
        selected_year = current_date.year
        selected_month = current_date.month
    
    # Get start and end date for the selected month
    start_date = datetime(selected_year, selected_month, 1).date()
    if selected_month == 12:
        end_date = datetime(selected_year + 1, 1, 1).date() - timedelta(days=1)
    else:
        end_date = datetime(selected_year, selected_month + 1, 1).date() - timedelta(days=1)
    
    # Get temperature data for the selected month
    temp_data = db.get_temperature_data(start_date, end_date)
    
    # Format temperature data for display
    formatted_temp_data = []
    if temp_data:
        for temp in temp_data:
            # Convert date to string if it's a date object
            if isinstance(temp[0], date):
                date_str = temp[0].strftime('%Y-%m-%d')
            else:
                date_str = temp[0]
            
            formatted_temp_data.append({
                'date': date_str,
                'display_date': datetime.strptime(date_str, '%Y-%m-%d').strftime('%d %B %Y'),
                'outdoor_temp': temp[1]
            })
    
    # Get all years with temperature data for the year selector
    all_years = set()
    all_temp_data = db.get_temperature_data(
        datetime(2000, 1, 1).date(),  # Start from year 2000
        datetime(2100, 1, 1).date()   # End at year 2100
    )
    
    if all_temp_data:
        for temp in all_temp_data:
            if isinstance(temp[0], date):
                all_years.add(temp[0].year)
            elif isinstance(temp[0], str):
                try:
                    year = datetime.strptime(temp[0], '%Y-%m-%d').year
                    all_years.add(year)
                except ValueError:
                    pass
    
    # Sort years in descending order
    years_list = sorted(list(all_years), reverse=True)
    
    # If no years found, add current year
    if not years_list:
        years_list = [current_date.year]
    
    # Clean up
    db.close_connection()
    
    return render_template('temperature/edit.html', 
                           temp_data=formatted_temp_data,
                           years=years_list,
                           selected_year=selected_year,
                           selected_month=selected_month,
                           current_year=current_date.year,
                           current_month=current_date.month,
                           active_page='temperature')
