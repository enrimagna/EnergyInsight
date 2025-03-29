# Deployment Guide

This document outlines how to deploy the EnergyInsight application for production use.

## Deployment Options

### Docker Deployment (Recommended)

The application is containerized using Docker, making deployment simple and consistent across environments.

1. **Start the Application**:
   ```bash
   docker-compose up -d
   ```
   This will start the application in detached mode.

2. **Verify Deployment**:
   ```bash
   docker-compose ps
   ```
   Ensure the container is running properly.

3. **Access the Application**:
   The application will be available at http://localhost:5000 by default.

### Production Considerations

For a production environment, consider the following adjustments:

1. **Environment Variables**:
   - Set `DEBUG=False` in your `.env` file
   - Generate a strong `SECRET_KEY`
   - Secure your credentials

2. **Reverse Proxy**:
   For production, place the application behind a reverse proxy like Nginx:
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;

       location / {
           proxy_pass http://localhost:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

3. **HTTPS**:
   Configure SSL/TLS with Let's Encrypt for secure connections.

## Scheduled Tasks

The application uses APScheduler to automatically run periodic tasks:

- **Energy Data Collection**: Runs every 30 minutes to collect energy data from MELCloud
- **Temperature Data Collection**: Runs alongside energy collection to gather temperature data
- **Price Updates**: Runs daily to ensure price information is current

These scheduled tasks are configured in `app/__init__.py` and will start automatically when the application runs.

## Logging

Logs are sent to the standard output and can be viewed with:
```bash
docker-compose logs -f
```

## Backup

To backup the database:
```bash
docker cp energyinsight_app_1:/app/app/db/energy_data.db ./backup/energy_data_$(date +%Y%m%d).db
```

## Monitoring

For production deployments, consider adding:
- Container health monitoring
- Database backup automation
- External uptime monitoring

## Updating the Application

To update the application:
```bash
git pull
docker-compose down
docker-compose up -d --build
```

This will rebuild the container with the latest code changes.
