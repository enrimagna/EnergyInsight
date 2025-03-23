import os
import logging
import asyncio
from flask import Flask, session, request
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from app.db.models import Database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app(test_config=None):
    # Create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    
    # Load environment variables
    load_dotenv()
    
    # Set a basic secret key for development
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key-for-testing-only')
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
    # Disable CSRF protection entirely for simplicity
    app.config['WTF_CSRF_ENABLED'] = False
    
    # Ensure the database directory exists
    db_dir = os.path.join(os.path.dirname(__file__), 'db')
    os.makedirs(db_dir, exist_ok=True)
    
    # Initialize database
    db = Database()
    db.create_tables()
    
    # Set up scheduler for data collection
    try:
        scheduler = BackgroundScheduler()
        
        # Import here to avoid circular imports
        from app.data_fetchers import fetch_all_data, update_prices
        
        # Schedule data fetching (every 30 minutes)
        scheduler.add_job(
            lambda: asyncio.run(fetch_all_data()),
            'interval', 
            minutes=30,
            id='fetch_data'
        )
        
        # Schedule price updates (once a day)
        scheduler.add_job(
            update_prices,
            'interval',
            hours=24,
            id='update_prices'
        )
        
        # Start the scheduler
        scheduler.start()
        logger.info("Scheduled tasks started")
    except Exception as e:
        logger.warning(f"Could not set up scheduler: {e}")
        logger.info("Continuing without scheduler - you'll need to trigger data updates manually")
    
    # Register blueprints
    from app.routes import dashboard, settings, data
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(settings.bp, url_prefix='/settings')
    app.register_blueprint(data.bp, url_prefix='/data')
    
    # Add global context processors
    @app.context_processor
    def inject_current_date():
        return {'current_date': datetime.now()}
    
    # Ensure CSRF token is available for all templates
    @app.before_request
    def make_session_permanent():
        session.permanent = True
    
    return app
