# Use Python 3.9 as base
FROM python:3.9-slim

# Install Node.js (for building frontend)
RUN apt-get update && apt-get install -y nodejs npm

# Set working directory
WORKDIR /app

# Copy Backend Requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Project Files
COPY . .

# Build Frontend
WORKDIR /app/web_ui
RUN npm install
RUN npm run build

# Go back to root
WORKDIR /app

# Expose Port (Render sets this)
ENV PORT=8000
EXPOSE $PORT

# Start Command
CMD ["sh", "-c", "uvicorn api_server:app --host 0.0.0.0 --port $PORT"]
