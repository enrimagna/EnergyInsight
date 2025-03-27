from flask import Blueprint, render_template, request
import json
import logging
from datetime import datetime, timedelta
from app.db.models import Database

logger = logging.getLogger(__name__)
bp = Blueprint('dashboard', __name__)

@bp.route('/')
def index():
    """Main dashboard view showing all energy and temperature data."""
    # Get time range from request
    days = request.args.get('days', default=7, type=int)
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Get data from database
    db = Database()
    energy_data = db.get_energy_data(start_date, end_date)
    temp_data = db.get_temperature_data(start_date, end_date)
    
    # Debug: Log the data retrieved
    logger.info(f"Retrieved {len(energy_data) if energy_data else 0} energy data points")
    logger.info(f"Retrieved {len(temp_data) if temp_data else 0} temperature data points")
    
    # Create chart data
    charts = {}
    
    # Energy consumption chart
    if energy_data:
        # Convert timestamp strings to datetime objects if needed
        timestamps = []
        for row in energy_data:
            if isinstance(row[0], str):
                # If timestamp is a string, format it directly
                timestamps.append(row[0])
            else:
                # If timestamp is a datetime object, format it
                timestamps.append(row[0].strftime('%Y-%m-%d %H:%M'))
                
        power_values = [float(row[1]) for row in energy_data]
        energy_values = [float(row[2]) for row in energy_data]
        
        energy_chart = {
            'type': 'line',
            'data': {
                'labels': timestamps,
                'datasets': [
                    {
                        'label': 'Power (kW)',
                        'data': power_values,
                        'borderColor': 'rgb(75, 192, 192)',
                        'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                        'yAxisID': 'y',
                        'tension': 0.1
                    },
                    {
                        'label': 'Energy (kWh)',
                        'data': energy_values,
                        'borderColor': 'rgb(255, 99, 132)',
                        'backgroundColor': 'rgba(255, 99, 132, 0.2)',
                        'yAxisID': 'y1',
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
                'stacked': False,
                'scales': {
                    'y': {
                        'type': 'linear',
                        'display': True,
                        'position': 'left',
                        'title': {
                            'display': True,
                            'text': 'Power (kW)'
                        }
                    },
                    'y1': {
                        'type': 'linear',
                        'display': True,
                        'position': 'right',
                        'title': {
                            'display': True,
                            'text': 'Energy (kWh)'
                        },
                        'grid': {
                            'drawOnChartArea': False
                        }
                    }
                },
                'plugins': {
                    'title': {
                        'display': True,
                        'text': 'Energy Consumption'
                    }
                }
            }
        }
        charts['energy_chart'] = json.dumps(energy_chart)
        logger.info(f"Energy chart data created with {len(timestamps)} points")
    else:
        logger.warning("No energy data available to create chart")
    
    # Cost comparison chart
    if energy_data:
        # Get prices from database instead of environment variables
        price_data = db.get_current_prices()
        
        if price_data:
            electricity_price = price_data['electricity_price']
            diesel_price = price_data['diesel_price']
            diesel_efficiency = price_data['diesel_efficiency']
            logger.info(f"Dashboard using prices from DB - Electricity: {electricity_price}, Diesel: {diesel_price}, Efficiency: {diesel_efficiency}")
        else:
            # Fallback to default values if no prices in database
            electricity_price = 0.28
            diesel_price = 1.50
            diesel_efficiency = 0.85
            logger.warning(f"No prices found in DB, using defaults - Electricity: {electricity_price}, Diesel: {diesel_price}, Efficiency: {diesel_efficiency}")
        
        # Calculate costs
        # Convert timestamp strings to datetime objects if needed
        timestamps = []
        for row in energy_data:
            if isinstance(row[0], str):
                # If timestamp is a string, format it directly
                timestamps.append(row[0])
            else:
                # If timestamp is a datetime object, format it
                timestamps.append(row[0].strftime('%Y-%m-%d %H:%M'))
                
        electricity_costs = [float(row[3]) for row in energy_data]
        
        # Diesel equivalent cost calculation
        # Assuming the heat pump COP (Coefficient of Performance) is around 3
        # So for each kWh of electricity, we get 3 kWh of heat
        heat_pump_cop = 3.0
        energy_values = [float(row[2]) for row in energy_data]
        heat_output = [e * heat_pump_cop for e in energy_values]
        
        # Diesel energy content is about 10 kWh per liter
        diesel_energy_content = 10.0  # kWh/liter
        diesel_liters = [h / (diesel_energy_content * diesel_efficiency) for h in heat_output]
        diesel_costs = [d * diesel_price for d in diesel_liters]
        
        # Cumulative costs
        cum_electricity = [sum(electricity_costs[:i+1]) for i in range(len(electricity_costs))]
        cum_diesel = [sum(diesel_costs[:i+1]) for i in range(len(diesel_costs))]
        
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
                        'text': f"Cumulative Cost Comparison (Electricity: {electricity_price}€/kWh, Diesel: {diesel_price}€/L)"
                    },
                    'tooltip': {
                        'callbacks': {
                            'label': 'function(context) { return context.dataset.label + ": " + context.parsed.y.toFixed(2) + "€"; }'
                        }
                    }
                }
            }
        }
        charts['cost_chart'] = json.dumps(cost_chart)
        logger.info(f"Cost chart data created with {len(timestamps)} points")
    else:
        logger.warning("No energy data available to create cost chart")
    
    # Temperature chart
    if temp_data:
        # Convert timestamp strings to datetime objects if needed
        timestamps = []
        for row in temp_data:
            if isinstance(row[0], str):
                # If timestamp is a string, format it directly
                timestamps.append(row[0])
            else:
                # If timestamp is a datetime object, format it
                timestamps.append(row[0].strftime('%Y-%m-%d %H:%M'))
                
        indoor_temps = [float(row[1]) for row in temp_data]
        outdoor_temps = [float(row[2]) for row in temp_data]
        
        temp_chart = {
            'type': 'line',
            'data': {
                'labels': timestamps,
                'datasets': [
                    {
                        'label': 'Indoor Temperature (°C)',
                        'data': indoor_temps,
                        'borderColor': 'rgb(153, 102, 255)',
                        'backgroundColor': 'rgba(153, 102, 255, 0.2)',
                        'tension': 0.1
                    },
                    {
                        'label': 'Outdoor Temperature (°C)',
                        'data': outdoor_temps,
                        'borderColor': 'rgb(201, 203, 207)',
                        'backgroundColor': 'rgba(201, 203, 207, 0.2)',
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
    
    # Get current prices for display in the dashboard
    current_prices = {
        'electricity_price': electricity_price if 'electricity_price' in locals() else 0.28,
        'diesel_price': diesel_price if 'diesel_price' in locals() else 1.50,
        'diesel_efficiency': diesel_efficiency if 'diesel_efficiency' in locals() else 0.85
    }
    
    # Debug: Log the charts being passed to the template
    logger.info(f"Passing {len(charts)} charts to template: {', '.join(charts.keys())}")
    
    # Ensure current_date is a datetime object
    current_date = datetime.now()
    
    return render_template(
        'dashboard/index.html', 
        charts=charts,
        current_prices=current_prices,
        current_date=current_date,
        timedelta=timedelta
    )
