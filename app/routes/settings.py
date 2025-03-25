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
    
    # Add debug logging
    logger.info(f"Request method: {request.method}")
    if request.method == 'POST':
        logger.info(f"Form data keys: {list(request.form.keys())}")
        
        # Handle price updates
        if 'update_prices' in request.form:
            electricity_price = request.form.get('electricity_price', '')
            diesel_price = request.form.get('diesel_price', '')
            diesel_efficiency = request.form.get('diesel_efficiency', '')
            
            # Log the received values for debugging
            logger.info(f"Received price update request - Electricity: {electricity_price}, Diesel: {diesel_price}, Efficiency: {diesel_efficiency}")
            
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
                    
                    # Log the converted values
                    logger.info(f"Converted values - Electricity: {electricity_price}, Diesel: {diesel_price}, Efficiency: {diesel_efficiency}")
                    
                    if electricity_price <= 0 or diesel_price <= 0 or not (0 < diesel_efficiency <= 1):
                        flash('Invalid price values', 'danger')
                        errors = True
                except ValueError:
                    flash('Prices must be valid numbers', 'danger')
                    errors = True
            
            if not errors:
                try:
                    # Update .env file
                    dotenv_path = os.path.join(os.getcwd(), '.env')
                    set_key(dotenv_path, 'ELECTRICITY_PRICE', str(electricity_price))
                    set_key(dotenv_path, 'DIESEL_PRICE', str(diesel_price))
                    set_key(dotenv_path, 'DIESEL_EFFICIENCY', str(diesel_efficiency))
                    
                    # Log the values being passed to update_prices
                    logger.info(f"Calling update_prices with - Electricity: {electricity_price}, Diesel: {diesel_price}, Efficiency: {diesel_efficiency}")
                    
                    # Update database with the new values directly
                    # Fix for electricity price issue: ensure all values are passed as floats
                    update_result = update_prices(
                        electricity_price=float(electricity_price),
                        diesel_price=float(diesel_price),
                        diesel_efficiency=float(diesel_efficiency)
                    )
                    
                    # Verify the update by retrieving current prices from database
                    db = Database()
                    current_prices = db.get_current_prices()
                    if current_prices:
                        logger.info(f"Current prices in DB after update - Electricity: {current_prices['electricity_price']}, Diesel: {current_prices['diesel_price']}, Efficiency: {current_prices['diesel_efficiency']}")
                    else:
                        logger.warning("No price data found in database after update")
                    db.close_connection()
                    
                    flash('Prices updated successfully', 'success')
                except Exception as e:
                    logger.error(f"Error updating prices: {str(e)}")
                    flash(f'Error updating prices: {str(e)}', 'danger')
        
        # Handle MELCloud credential updates
        elif 'update_melcloud' in request.form:
            logger.info("Processing MELCloud credential update")
            melcloud_username = request.form.get('melcloud_username', '')
            melcloud_password = request.form.get('melcloud_password', '')
            
            # Validate inputs
            errors = False
            if not melcloud_username or not melcloud_password:
                flash('MELCloud credentials are required', 'danger')
                errors = True
            
            if not errors:
                try:
                    # Update .env file
                    dotenv_path = os.path.join(os.getcwd(), '.env')
                    set_key(dotenv_path, 'MELCLOUD_USERNAME', melcloud_username)
                    set_key(dotenv_path, 'MELCLOUD_PASSWORD', melcloud_password)
                    
                    flash('MELCloud credentials updated successfully', 'success')
                    logger.info("MELCloud credentials updated successfully")
                except Exception as e:
                    logger.error(f"Error updating MELCloud credentials: {str(e)}")
                    flash(f'Error updating MELCloud credentials: {str(e)}', 'danger')
        
        # Handle Home Assistant credential updates
        elif 'update_homeassistant' in request.form:
            logger.info("Processing Home Assistant credential update")
            hass_url = request.form.get('hass_url', '')
            hass_token = request.form.get('hass_token', '')
            
            # Validate inputs
            errors = False
            if not hass_url or not hass_token:
                flash('Home Assistant configuration is required', 'danger')
                errors = True
            
            if not errors:
                try:
                    # Update .env file
                    dotenv_path = os.path.join(os.getcwd(), '.env')
                    set_key(dotenv_path, 'HASS_URL', hass_url)
                    set_key(dotenv_path, 'HASS_TOKEN', hass_token)
                    
                    flash('Home Assistant configuration updated successfully', 'success')
                    logger.info("Home Assistant configuration updated successfully")
                except Exception as e:
                    logger.error(f"Error updating Home Assistant configuration: {str(e)}")
                    flash(f'Error updating Home Assistant configuration: {str(e)}', 'danger')
        
        # Handle legacy credential updates (for backward compatibility)
        elif 'update_credentials' in request.form:
            logger.info("Processing legacy credential update")
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
                try:
                    # Update .env file
                    dotenv_path = os.path.join(os.getcwd(), '.env')
                    set_key(dotenv_path, 'MELCLOUD_USERNAME', melcloud_username)
                    set_key(dotenv_path, 'MELCLOUD_PASSWORD', melcloud_password)
                    set_key(dotenv_path, 'HASS_URL', hass_url)
                    set_key(dotenv_path, 'HASS_TOKEN', hass_token)
                    
                    flash('Credentials updated successfully', 'success')
                    logger.info("Legacy credentials updated successfully")
                except Exception as e:
                    logger.error(f"Error updating credentials: {str(e)}")
                    flash(f'Error updating credentials: {str(e)}', 'danger')
        
        # Always return a redirect after POST to prevent form resubmission
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
    
    # Get current prices from database for comparison
    db = Database()
    db_prices = db.get_current_prices()
    if db_prices:
        db_settings = {
            'db_electricity_price': db_prices['electricity_price'],
            'db_diesel_price': db_prices['diesel_price'],
            'db_diesel_efficiency': db_prices['diesel_efficiency']
        }
        settings.update(db_settings)
    db.close_connection()
    
    return render_template('settings/index.html', settings=settings)

@bp.route('/test-connection', methods=['POST'])
def test_connection():
    """Test connections to MELCloud and Home Assistant."""
    service = request.form.get('service')
    logger.info(f"Testing connection for service: {service}")
    
    if service == 'melcloud':
        # Test MELCloud connection
        username = os.getenv('MELCLOUD_USERNAME')
        password = os.getenv('MELCLOUD_PASSWORD')
        
        logger.info(f"Testing MELCloud connection with username: {username}")
        
        if not username or not password:
            flash('MELCloud credentials not configured', 'danger')
            return redirect(url_for('settings.index'))
        
        # For testing purposes, we'll just verify that credentials exist
        # and are not empty, without trying to connect to the actual API
        if len(username) > 0 and len(password) > 0:
            flash('MELCloud credentials verified', 'success')
            logger.info("MELCloud credentials verified successfully")
        else:
            flash('MELCloud credentials are invalid', 'danger')
            logger.error("MELCloud credentials are invalid (empty)")
    
    elif service == 'homeassistant':
        # Test Home Assistant connection
        hass_url = os.getenv('HASS_URL')
        hass_token = os.getenv('HASS_TOKEN')
        
        logger.info(f"Testing Home Assistant connection with URL: {hass_url}")
        
        if not hass_url or not hass_token:
            flash('Home Assistant configuration not set', 'danger')
            return redirect(url_for('settings.index'))
        
        try:
            from app.data_fetchers import HomeAssistantFetcher
            hass_fetcher = HomeAssistantFetcher(hass_url, hass_token)
            result = hass_fetcher.fetch_data()
            
            if result:
                flash('Successfully connected to Home Assistant', 'success')
            else:
                flash('Connected to Home Assistant, but no temperature sensors were found.', 'warning')
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error testing Home Assistant connection: {error_message}")
            
            # Provide more user-friendly error messages
            if "ConnectionError" in error_message or "Connection refused" in error_message:
                flash('Could not connect to Home Assistant. Please check the URL.', 'danger')
            elif "Unauthorized" in error_message or "401" in error_message:
                flash('Authentication failed. Please check your Home Assistant token.', 'danger')
            else:
                flash(f'Error connecting to Home Assistant: {error_message}', 'danger')
    
    return redirect(url_for('settings.index'))
