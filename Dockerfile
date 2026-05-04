# Use Playwright's official Python image which includes necessary browser binaries
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set environment variables
ENV PYTHONUNBUFFERED=True
ENV APP_HOME=/app
WORKDIR $APP_HOME

# Copy requirements and install
COPY requirements.txt ./
# Also install Flask and gunicorn for the web server
RUN pip install --no-cache-dir -r requirements.txt Flask gunicorn

# Install playwright browsers (though the base image should have them)
RUN playwright install chromium

# Copy local code to the container image
COPY . ./

# Run the web service on container startup
# Set timeout to 3600 seconds (1 hour) to match max Cloud Run timeout for the long-running schedule
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 3600 app:app
