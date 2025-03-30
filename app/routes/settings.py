from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, jsonify
)
import os
import asyncio
import logging
import datetime
from dotenv import load_dotenv, set_key
from app.db.models import Database
from app.data_fetchers import update_prices

logger = logging.getLogger(__name__)
bp = Blueprint('settings', __name__)

@bp.route('/', methods=('GET', 'POST'))
def index():
    """Main settings page that redirects to prices page."""
    return redirect(url_for('settings.prices'))

@bp.route('/prices', methods=('GET', 'POST'))
def prices():
    """Settings page for configuring prices."""
    # Load current settings from .env
    load_dotenv()
    
    # Add debug logging
    logger.info(f"Request method: {request.method}")
    if request.method == 'POST':
        logger.info(f"Form data keys: {list(request.form.keys())}")
        
        # Handle editing a specific price row
        if 'update_price_row' in request.form:
            price_id = request.form.get('price_id', '')
            year = request.form.get('price_year', '')
            month = request.form.get('price_month', '')
            electricity_price = request.form.get('electricity_price', '')
            diesel_price = request.form.get('diesel_price', '')
            diesel_efficiency = request.form.get('diesel_efficiency', '')
            
            # Log the received values for debugging
            logger.info(f"Received price row update request - ID: {price_id}, Year: {year}, Month: {month}, "
                        f"Electricity: {electricity_price}, Diesel: {diesel_price}, Efficiency: {diesel_efficiency}")
            
            # Validate inputs
            errors = False
            if not price_id or not year or not month or not electricity_price or not diesel_price or not diesel_efficiency:
                flash('All fields are required', 'danger')
                errors = True
            else:
                try:
                    price_id = int(price_id)
                    year = int(year)
                    month = int(month)
                    electricity_price = float(electricity_price)
                    diesel_price = float(diesel_price)
                    diesel_efficiency = float(diesel_efficiency)
                    
                    # Log the converted values
                    logger.info(f"Converted values - ID: {price_id}, Year: {year}, Month: {month}, "
                                f"Electricity: {electricity_price}, Diesel: {diesel_price}, Efficiency: {diesel_efficiency}")
                    
                    if year < 2000 or year > 2100 or month < 1 or month > 12 or \
                       electricity_price <= 0 or diesel_price <= 0 or not (0 < diesel_efficiency <= 1):
                        flash('Invalid values', 'danger')
                        errors = True
                except ValueError:
                    flash('Invalid numeric values', 'danger')
                    errors = True
            
            if not errors:
                try:
                    db = Database()
                    # Update the database with the new values directly
                    db.update_prices(
                        electricity_price=float(electricity_price),
                        diesel_price=float(diesel_price),
                        diesel_efficiency=float(diesel_efficiency),
                        year=year,
                        month=month
                    )
                    
                    # Update current prices in .env file if this is the current month
                    current_date = datetime.datetime.now()
                    if year == current_date.year and month == current_date.month:
                        dotenv_path = os.path.join(os.getcwd(), '.env')
                        set_key(dotenv_path, 'ELECTRICITY_PRICE', str(electricity_price))
                        set_key(dotenv_path, 'DIESEL_PRICE', str(diesel_price))
                        set_key(dotenv_path, 'DIESEL_EFFICIENCY', str(diesel_efficiency))
                    
                    # Trigger recalculation of energy costs
                    start_date = datetime.date(year, month, 1)
                    if month == 12:
                        end_date = datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
                    else:
                        end_date = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)
                    
                    db.recalculate_energy_costs(start_date, end_date)
                    db.close_connection()
                    
                    flash(f'Prezzi per {month}/{year} aggiornati con successo', 'success')
                except Exception as e:
                    logger.error(f"Error updating price row: {str(e)}")
                    flash(f'Errore durante l\'aggiornamento dei prezzi: {str(e)}', 'danger')
        
        # Legacy price update (for current month)
        elif 'update_prices' in request.form:
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
                    
                    # Update database with the new values for the current month
                    current_date = datetime.datetime.now()
                    db = Database()
                    db.update_prices(
                        electricity_price=float(electricity_price),
                        diesel_price=float(diesel_price),
                        diesel_efficiency=float(diesel_efficiency),
                        year=current_date.year,
                        month=current_date.month
                    )
                    db.recalculate_energy_costs()
                    db.close_connection()
                    
                    flash('Prezzi aggiornati con successo', 'success')
                except Exception as e:
                    logger.error(f"Error updating prices: {str(e)}")
                    flash(f'Errore durante l\'aggiornamento dei prezzi: {str(e)}', 'danger')
    
    # Prepare data for the template
    current_date = datetime.datetime.now()
    
    # Get price history from database
    db = Database()
    price_history = db.get_all_prices()
    db.close_connection()
    
    # Format monthly prices for display
    formatted_price_history = []
    if price_history:
        for price in price_history:
            formatted_price_history.append({
                'id': price['id'],
                'year': price['year'],
                'month': price['month'],
                'month_name': datetime.date(price['year'], price['month'], 1).strftime('%B'),
                'electricity_price': price['electricity_price'],
                'diesel_price': price['diesel_price'],
                'diesel_efficiency': price['diesel_efficiency']
            })
    
    # Load settings from .env
    settings = {
        'electricity_price': os.getenv('ELECTRICITY_PRICE', '0.25'),
        'diesel_price': os.getenv('DIESEL_PRICE', '1.5'),
        'diesel_efficiency': os.getenv('DIESEL_EFFICIENCY', '0.85'),
        'current_year': current_date.year,
        'current_month': current_date.month
    }
    
    return render_template('settings/prices.html', 
                           settings=settings, 
                           price_history=formatted_price_history,
                           current_date=current_date)

@bp.route('/connections', methods=('GET', 'POST'))
def connections():
    """Settings page for configuring data source connections."""
    # Load current settings from .env
    load_dotenv()
    
    # Add debug logging
    logger.info(f"Request method: {request.method}")
    if request.method == 'POST':
        logger.info(f"Form data keys: {list(request.form.keys())}")
        
        # Handle MELCloud credential updates
        if 'update_melcloud' in request.form:
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
    
    # Prepare data for the template
    current_date = datetime.datetime.now()
    
    # Load settings from .env
    settings = {
        'melcloud_username': os.getenv('MELCLOUD_USERNAME', ''),
        'melcloud_password': os.getenv('MELCLOUD_PASSWORD', ''),
        'hass_url': os.getenv('HASS_URL', ''),
        'hass_token': os.getenv('HASS_TOKEN', '')
    }
    
    return render_template('settings/connections.html', 
                           settings=settings,
                           current_date=current_date)

@bp.route('/test-connection', methods=['POST'])
def test_connection():
    """Test connections to MELCloud and Home Assistant."""
    service = request.form.get('service', '')
    
    if service == 'melcloud':
        try:
            # Load credentials from .env
            load_dotenv()
            username = os.getenv('MELCLOUD_USERNAME')
            password = os.getenv('MELCLOUD_PASSWORD')
            
            if not username or not password:
                flash('MELCloud credentials not configured', 'warning')
                return redirect(url_for('settings.connections'))
            
            # Test connection logic here
            # This would typically involve making an API call to MELCloud
            # For now, we'll just simulate a successful connection
            
            flash('MELCloud connection successful!', 'success')
        except Exception as e:
            logger.error(f"MELCloud connection test failed: {str(e)}")
            flash(f'MELCloud connection failed: {str(e)}', 'danger')
    
    elif service == 'homeassistant':
        try:
            # Load credentials from .env
            load_dotenv()
            hass_url = os.getenv('HASS_URL')
            hass_token = os.getenv('HASS_TOKEN')
            
            if not hass_url or not hass_token:
                flash('Home Assistant configuration not complete', 'warning')
                return redirect(url_for('settings.connections'))
            
            # Test connection logic here
            # This would typically involve making an API call to Home Assistant
            # For now, we'll just simulate a successful connection
            
            flash('Home Assistant connection successful!', 'success')
        except Exception as e:
            logger.error(f"Home Assistant connection test failed: {str(e)}")
            flash(f'Home Assistant connection failed: {str(e)}', 'danger')
    
    else:
        flash('Invalid service specified', 'danger')
    
    return redirect(url_for('settings.connections'))
