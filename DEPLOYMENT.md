# Deployment Guide for EnergyInsight

## Docker Deployment

EnergyInsight can be easily deployed using Docker and docker-compose. Follow these steps:

### 1. Configure Environment Variables

Before deploying, you need to set up your environment variables in a `.env` file. A template is provided in `.env.example`.

```bash
# Copy the example .env file
cp .env.example .env

# Edit the .env file with your credentials
nano .env
```

Make sure to fill in:
- MELCloud credentials (username, password, and optionally device ID)
- Home Assistant credentials (URL and access token)
- Time zone setting (default: Europe/Rome)

### 2. Prepare Database Directory

Ensure the database directory exists:

```bash
mkdir -p app/db
mkdir -p logs
```

### 3. Using Existing Database

If you already have a database file (`energy_data.db`), you can use it with Docker by placing it in the `app/db` directory before starting the containers:

```bash
# Copy your existing database to the app/db directory
cp /path/to/your/energy_data.db app/db/
```

The database file will be mounted as a volume, so your data will persist even if the container is restarted.

### 4. Start the Docker Containers

Run the following command to build and start the containers:

```bash
docker-compose up -d
```

This will start:
- The web application on port 5000
- The data collector service running in the background

### 5. Monitor the Service

You can check the logs of the data collector service:

```bash
# View the data collector logs
cat logs/collector.log
```

Or follow the logs in real-time:

```bash
# Follow the data collector logs
tail -f logs/collector.log
```

### 6. Accessing the Application

Once deployed, you can access the web interface at:

```
http://your-server-ip:5000
```

## Features of the Data Collector Service

The service automatically:

1. Checks for missing data in the last 180 days
2. Collects energy data from MELCloud
3. Collects temperature data from Home Assistant
4. Creates new price entries for each month
5. Runs checks every 24 hours by default
6. Retries failed API requests

## Customizing the Service

You can customize the data collector service by editing the environment variables or the startup script in the Dockerfile. Key parameters include:

- `--days-to-check`: Number of days to check for missing data (default: 180)
- `--retry-hours`: Hours to wait before retrying failed requests (default: 2)
- `--check-interval-hours`: Hours between data checks (default: 24)

## Troubleshooting

### Database Issues

If you encounter issues with the database:

```bash
# Stop the containers
docker-compose down

# Check database permissions
ls -la app/db/

# Ensure the Docker user can access the database
chmod 666 app/db/energy_data.db
```

### API Connection Issues

If the service cannot connect to MELCloud or Home Assistant:

1. Verify your credentials in the `.env` file
2. Check if the services are accessible from the Docker container
3. Review the logs for specific error messages

### Updating the Application

To update the application to a new version:

```bash
# Pull the latest code
git pull

# Rebuild and restart the containers
docker-compose down
docker-compose up -d --build
```
