FROM python:3.11-slim

# Prevent Python from buffering logs
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app
COPY . .

# Fly.io exposes port 8080 by default
EXPOSE 8080

# Start the app with gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]
