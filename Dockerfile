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

# Install system dependencies (e.g. libpq for Postgres, curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root application user for least privilege security
RUN useradd -m -u 1000 appuser

# Copy backend requirements and install
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and compiled static assets
COPY courtos/ ./courtos/
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Set file ownership for appuser
RUN chown -R appuser:appuser /app

# Expose default Cloud Run port
ENV PORT=8080
EXPOSE 8080

# Switch to non-root user
USER appuser

# Container Health Check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8080}/api/v1/health || exit 1

# Execute uvicorn using exec shell form to ensure SIGTERM signals reach Python process
CMD ["sh", "-c", "exec uvicorn courtos.app:app --host 0.0.0.0 --port ${PORT:-8080}"]

