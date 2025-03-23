from app import create_app
from dotenv import load_dotenv
import os
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Ensure database directory exists
db_dir = os.path.join("app", "db")
Path(db_dir).mkdir(parents=True, exist_ok=True)

# Create a .env file if it doesn't exist
if not os.path.exists('.env'):
    with open('.env', 'w') as f:
        try:
            with open('.env.example', 'r') as example:
                f.write(example.read())
            logger.info("Created .env file from .env.example. Please update with your actual credentials.")
        except FileNotFoundError:
            # If .env.example doesn't exist, create basic config
            f.write("""# Basic configuration
MELCLOUD_USERNAME=your_email@example.com
MELCLOUD_PASSWORD=your_password
HASS_URL=http://your-homeassistant:8123
HASS_TOKEN=your_long_lived_access_token
ELECTRICITY_PRICE=0.28
DIESEL_PRICE=1.50
DIESEL_EFFICIENCY=0.85
DATABASE_PATH=app/db/energy_data.db
SECRET_KEY=your_secret_key_here
DEBUG=True
""")
            logger.info("Created basic .env file. Please update with your actual credentials.")

# Try to generate test data if database is empty
try:
    db_path = os.path.join("app", "db", "energy_data.db")
    if not os.path.exists(db_path) or os.path.getsize(db_path) < 1024:
        logger.info("Database appears empty. Attempting to generate test data...")
        try:
            import generate_test_data
            logger.info("Test data generated successfully!")
        except ImportError as e:
            logger.warning(f"Could not import generate_test_data module: {e}")
        except Exception as e:
            logger.warning(f"Error generating test data: {e}")
except Exception as e:
    logger.warning(f"Error checking database: {e}")

# Import Flask app
try:
    from app import create_app
    app = create_app()
    
    if __name__ == '__main__':
        # Print info message
        logger.info("Starting EnergyInsight application...")
        logger.info("Access the application at http://localhost:5000")
        
        # Run the app
        app.run(host='0.0.0.0', port=5000, debug=True)
        
except ImportError as e:
    print(f"""
ERROR: {e}

It looks like you're missing some required dependencies. 
Try installing the minimal dependencies with:

pip install flask flask-wtf python-dotenv requests plotly

or all dependencies with:

pip install -r requirements.txt

If you're still having issues, try:
1. Using a virtual environment: python -m venv venv
2. Activating it: venv\\Scripts\\activate
3. Installing dependencies: pip install -r requirements.txt
4. Running the app again: python run.py
""")
except Exception as e:
    print(f"""
ERROR: {e}

An unexpected error occurred when trying to start the application.
Please check the error message above for more details.
""")
