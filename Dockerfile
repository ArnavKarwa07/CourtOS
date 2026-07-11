# Stage 1: Build the React client assets
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Create Python runtime container
FROM python:3.12-slim
WORKDIR /app

# Install system dependencies (e.g. libpq for Postgres if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and compiled static assets
COPY courtos/ ./courtos/
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Expose default Cloud Run port
ENV PORT=8080
EXPOSE 8080

CMD uvicorn courtos.app:app --host 0.0.0.0 --port $PORT
