# EnergyInsight

A dashboard application for monitoring and analyzing energy consumption from various sources including MELCloud heat pumps and Home Assistant integrations.

## Features

- Integration with MELCloud for heat pump monitoring
- Home Assistant integration for additional energy data
- Energy cost calculations and comparisons
- Interactive dashboards with Plotly visualizations
- Docker support for easy deployment

## Requirements

- Python 3.9+
- Flask and related dependencies
- MELCloud account (for heat pump monitoring)
- Home Assistant instance (optional)

## Installation

### Local Development

1. Clone this repository
2. Create a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate  # Windows
   source venv/bin/activate  # Linux/Mac
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and update with your credentials:
   ```
   cp .env.example .env
   ```
5. Run the application:
   ```
   python run.py
   ```
6. Access the application at http://localhost:5000

### Docker Deployment

1. Make sure Docker and Docker Compose are installed
2. Copy `.env.example` to `.env` and update with your credentials
3. Build and start the container:
   ```
   docker-compose up -d
   ```
4. Access the application at http://localhost:5000

## Configuration

Update the `.env` file with your specific configuration:

- MELCloud credentials
- Home Assistant URL and access token
- Energy prices for cost calculations
- Database path
- Flask secret key

## License

MIT
