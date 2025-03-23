from flask import (
    Blueprint, render_template, request, redirect, url_for, flash
)
import os
import asyncio
import logging
from dotenv import load_dotenv, set_key
from app.db.models import Database
from app.data_fetchers import update_prices

logger = logging.getLogger(__name__)
bp = Blueprint('settings', __name__)

@bp.route('/', methods=('GET', 'POST'))
def index():
    """Settings page for configuring prices and credentials."""
    # Load current settings from .env
    load_dotenv()
    
    if request.method == 'POST':
        # Handle price updates
        if 'update_prices' in request.form:
            electricity_price = request.form.get('electricity_price', '')
            diesel_price = request.form.get('diesel_price', '')
            diesel_efficiency = request.form.get('diesel_efficiency', '')
            
            # Validate inputs
            errors = False
            if not electricity_price or not diesel_price or not diesel_efficiency:
                flash('All price fields are required', 'danger')
                errors = True
            else:
                try:
                    electricity_price = float(electricity_price)
                    diesel_price = float(diesel_price)
                    diesel_efficiency = float(diesel_efficiency)
                    
                    if electricity_price <= 0 or diesel_price <= 0 or not (0 < diesel_efficiency <= 1):
                        flash('Invalid price values', 'danger')
                        errors = True
                except ValueError:
                    flash('Prices must be valid numbers', 'danger')
                    errors = True
            
            if not errors:
                # Update .env file
                dotenv_path = os.path.join(os.getcwd(), '.env')
                set_key(dotenv_path, 'ELECTRICITY_PRICE', str(electricity_price))
                set_key(dotenv_path, 'DIESEL_PRICE', str(diesel_price))
                set_key(dotenv_path, 'DIESEL_EFFICIENCY', str(diesel_efficiency))
                
                # Update database with the new values directly
                update_prices(
                    electricity_price=electricity_price,
                    diesel_price=diesel_price,
                    diesel_efficiency=diesel_efficiency
                )
                
                flash('Prices updated successfully', 'success')
        
        # Handle credential updates
        elif 'update_credentials' in request.form:
            melcloud_username = request.form.get('melcloud_username', '')
            melcloud_password = request.form.get('melcloud_password', '')
            hass_url = request.form.get('hass_url', '')
            hass_token = request.form.get('hass_token', '')
            
            # Validate inputs
            errors = False
            if not melcloud_username or not melcloud_password:
                flash('MELCloud credentials are required', 'danger')
                errors = True
            
            if not hass_url or not hass_token:
                flash('Home Assistant configuration is required', 'danger')
                errors = True
            
            if not errors:
                # Update .env file
                dotenv_path = os.path.join(os.getcwd(), '.env')
                set_key(dotenv_path, 'MELCLOUD_USERNAME', melcloud_username)
                set_key(dotenv_path, 'MELCLOUD_PASSWORD', melcloud_password)
                set_key(dotenv_path, 'HASS_URL', hass_url)
                set_key(dotenv_path, 'HASS_TOKEN', hass_token)
                
                flash('Credentials updated successfully', 'success')
        
        return redirect(url_for('settings.index'))
    
    # Get current settings
    settings = {
        'electricity_price': os.getenv('ELECTRICITY_PRICE', '0.28'),
        'diesel_price': os.getenv('DIESEL_PRICE', '1.50'),
        'diesel_efficiency': os.getenv('DIESEL_EFFICIENCY', '0.85'),
        'melcloud_username': os.getenv('MELCLOUD_USERNAME', ''),
        'melcloud_password': os.getenv('MELCLOUD_PASSWORD', ''),
        'hass_url': os.getenv('HASS_URL', ''),
        'hass_token': os.getenv('HASS_TOKEN', '')
    }
    
    return render_template('settings/index.html', settings=settings)

@bp.route('/test-connection', methods=['POST'])
def test_connection():
    """Test connections to MELCloud and Home Assistant."""
    from app.data_fetchers import MELCloudFetcher, HomeAssistantFetcher
    
    service = request.form.get('service')
    
    if service == 'melcloud':
        # Test MELCloud connection
        username = os.getenv('MELCLOUD_USERNAME')
        password = os.getenv('MELCLOUD_PASSWORD')
        
        if not username or not password:
            flash('MELCloud credentials not configured', 'danger')
            return redirect(url_for('settings.index'))
        
        mel_fetcher = MELCloudFetcher(username, password)
        try:
            # Run the async function in a new event loop
            async def test_mel():
                await mel_fetcher.fetch_data()
                return True
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            success = loop.run_until_complete(test_mel())
            loop.close()
            
            if success:
                flash('Successfully connected to MELCloud', 'success')
            else:
                flash('Error connecting to MELCloud', 'danger')
        except Exception as e:
            logger.error(f"Error testing MELCloud connection: {e}")
            flash(f'Error connecting to MELCloud: {str(e)}', 'danger')
    
    elif service == 'homeassistant':
        # Test Home Assistant connection
        hass_url = os.getenv('HASS_URL')
        hass_token = os.getenv('HASS_TOKEN')
        
        if not hass_url or not hass_token:
            flash('Home Assistant configuration not set', 'danger')
            return redirect(url_for('settings.index'))
        
        hass_fetcher = HomeAssistantFetcher(hass_url, hass_token)
        try:
            hass_fetcher.fetch_data()
            flash('Successfully connected to Home Assistant', 'success')
        except Exception as e:
            logger.error(f"Error testing Home Assistant connection: {e}")
            flash(f'Error connecting to Home Assistant: {str(e)}', 'danger')
    
    return redirect(url_for('settings.index'))
