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
        timestamps = []
        outdoor_temps = []
        
        for row in temp_data:
            # Format date
            if isinstance(row[0], str):
                timestamps.append(row[0])
            else:
                timestamps.append(row[0].strftime('%Y-%m-%d'))
            
            # Temperature values - only outdoor temperature is available
            outdoor_temps.append(float(row[1] or 0))
        
        temp_fig = go.Figure()
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
