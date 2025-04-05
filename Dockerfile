FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create .env file if it doesn't exist
RUN if [ ! -f .env ]; then cp .env.example .env; fi

# Set up database directory
RUN mkdir -p app/db
RUN mkdir -p logs

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=run.py

# Expose port
EXPOSE 5000

# Create a startup script
RUN echo '#!/bin/bash\n\
# Start the data collector service in the background\n\
python data_collector_service.py --check-interval-hours 24 > /app/logs/collector.log 2>&1 &\n\
\n\
# Start the web application\n\
exec gunicorn --bind 0.0.0.0:5000 run:app\n\
' > /app/start.sh

RUN chmod +x /app/start.sh

# Run startup script
CMD ["/app/start.sh"]
