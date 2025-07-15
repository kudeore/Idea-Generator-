# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Expose port (Cloud Run listens on $PORT)
ENV PORT=8080
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 app:app