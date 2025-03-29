# Project Setup and Installation

This document outlines how to set up the EnergyInsight application for both development and production environments.

## Prerequisites

- **Docker**: The application is containerized using Docker for easy deployment
- **Python 3.9+**: For local development outside of Docker
- **Git**: For source code management (optional)

## Environment Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd EnergyInsight
   ```

2. **Create .env file**:
   Copy the example environment file and modify it with your credentials:
   ```bash
   cp .env.example .env
   ```
   
   Edit the `.env` file with your actual credentials:
   - MELCloud username and password
   - Home Assistant URL and token
   - Energy and fuel prices
   - Other configuration settings

## Installation Methods

### Using Docker (Recommended)

The application is designed to run in Docker, which handles all dependencies and setup automatically:

1. Build and start the Docker container:
   ```bash
   docker-compose up --build
   ```

2. Access the application at http://localhost:5000

### Manual Installation (Development)

For local development without Docker:

1. Create a virtual environment:
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS/Linux
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python run.py
   ```

## Database Setup

The database will be automatically created and initialized when the application starts. If the database is empty, sample test data will be generated automatically.

To manually generate test data:
```bash
python generate_test_data.py
```

## Next Steps

After setting up the application, proceed to [Deployment](deployment.md) for production deployment instructions.