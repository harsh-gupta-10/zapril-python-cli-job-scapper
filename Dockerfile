# Stage 1: Build the React Admin Dashboard
FROM node:20-slim AS build-stage
WORKDIR /app/admin
COPY admin/package*.json ./
RUN npm install
COPY admin/ ./
RUN npm run build

# Stage 2: Python environment
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set environment variables
ENV PYTHONUNBUFFERED=True
ENV APP_HOME=/app
WORKDIR $APP_HOME

# Copy requirements and install
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt Flask gunicorn flask-cors

# Install playwright browsers
RUN playwright install chromium

# Copy local code
COPY . ./

# Copy built React files from Stage 1
COPY --from=build-stage /app/admin/dist ./admin/dist

# Run the web service
CMD exec gunicorn --bind :$PORT --workers 1 --threads 4 --timeout 3600 app:app
