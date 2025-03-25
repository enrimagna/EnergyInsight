from flask import Blueprint, render_template, request
import plotly.graph_objects as go
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
    
    # Create graphs
    graphs = {}
    
    # Energy consumption graph
    if energy_data:
        timestamps = [row[0] for row in energy_data]
        power_values = [row[1] for row in energy_data]
        energy_values = [row[2] for row in energy_data]
        
        energy_fig = go.Figure()
        energy_fig.add_trace(go.Scatter(
            x=timestamps, 
            y=power_values,
            mode='lines',
            name='Power (kW)'
        ))
        energy_fig.add_trace(go.Scatter(
            x=timestamps, 
            y=energy_values,
            mode='lines',
            name='Energy (kWh)',
            yaxis='y2'
        ))
        energy_fig.update_layout(
            title='Energy Consumption',
            xaxis_title='Date',
            yaxis_title='Power (kW)',
            yaxis2=dict(
                title='Energy (kWh)',
                overlaying='y',
                side='right'
            ),
            height=500
        )
        graphs['energy_graph'] = json.dumps(energy_fig.to_dict())
    
    # Cost comparison graph
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
        timestamps = [row[0] for row in energy_data]
        electricity_costs = [row[3] for row in energy_data]
        
        # Diesel equivalent cost calculation
        # Assuming the heat pump COP (Coefficient of Performance) is around 3
        # So for each kWh of electricity, we get 3 kWh of heat
        heat_pump_cop = 3.0
        energy_values = [row[2] for row in energy_data]
        heat_output = [e * heat_pump_cop for e in energy_values]
        
        # Diesel energy content is about 10 kWh per liter
        diesel_energy_content = 10.0  # kWh/liter
        diesel_liters = [h / (diesel_energy_content * diesel_efficiency) for h in heat_output]
        diesel_costs = [d * diesel_price for d in diesel_liters]
        
        # Cumulative costs
        cum_electricity = [sum(electricity_costs[:i+1]) for i in range(len(electricity_costs))]
        cum_diesel = [sum(diesel_costs[:i+1]) for i in range(len(diesel_costs))]
        
        cost_fig = go.Figure()
        cost_fig.add_trace(go.Scatter(
            x=timestamps, 
            y=cum_electricity,
            mode='lines',
            name='Heat Pump Cost (€)'
        ))
        cost_fig.add_trace(go.Scatter(
            x=timestamps, 
            y=cum_diesel,
            mode='lines',
            name='Diesel Cost (€)'
        ))
        cost_fig.update_layout(
            title=f'Cumulative Cost Comparison (Electricity: {electricity_price}€/kWh, Diesel: {diesel_price}€/L)',
            xaxis_title='Date',
            yaxis_title='Cost (€)',
            height=500
        )
        graphs['cost_graph'] = json.dumps(cost_fig.to_dict())
    
    # Temperature graph
    if temp_data:
        timestamps = [row[0] for row in temp_data]
        indoor_temps = [row[1] for row in temp_data]
        outdoor_temps = [row[2] for row in temp_data]
        
        temp_fig = go.Figure()
        temp_fig.add_trace(go.Scatter(
            x=timestamps, 
            y=indoor_temps,
            mode='lines',
            name='Indoor Temperature (°C)'
        ))
        temp_fig.add_trace(go.Scatter(
            x=timestamps, 
            y=outdoor_temps,
            mode='lines',
            name='Outdoor Temperature (°C)'
        ))
        temp_fig.update_layout(
            title='Temperature Trends',
            xaxis_title='Date',
            yaxis_title='Temperature (°C)',
            height=500
        )
        graphs['temp_graph'] = json.dumps(temp_fig.to_dict())
    
    # Get current prices for display in the dashboard
    current_prices = {
        'electricity_price': electricity_price if 'electricity_price' in locals() else 0.28,
        'diesel_price': diesel_price if 'diesel_price' in locals() else 1.50,
        'diesel_efficiency': diesel_efficiency if 'diesel_efficiency' in locals() else 0.85
    }
    
    return render_template('dashboard/index.html', graphs=graphs, current_prices=current_prices)
