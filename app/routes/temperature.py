from flask import Blueprint, render_template, request
import plotly.graph_objects as go
import json
import logging
from datetime import datetime, timedelta
from app.db.models import Database

logger = logging.getLogger(__name__)
bp = Blueprint('temperature', __name__)

@bp.route('/')
def index():
    """Temperature data view showing temperature trends."""
    # Get time range from request
    days = request.args.get('days', default=7, type=int)
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Get data from database
    db = Database()
    temp_data = db.get_temperature_data(start_date, end_date)
    
    # Create graphs
    graphs = {}
    
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
    
    return render_template('temperature/index.html', graphs=graphs)
