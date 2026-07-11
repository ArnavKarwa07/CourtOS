#!/usr/bin/env bash
set -eo pipefail

# Configuration
GCP_PROJECT="courtos-production"
GCP_REGION="us-central1"
SERVICE_NAME="courtos-api"
IMAGE_TAG="gcr.io/${GCP_PROJECT}/${SERVICE_NAME}:latest"

echo "=== 1. Building React SPA Frontend ==="
cd frontend
npm install
npm run build
cd ..

echo "=== 2. Building and Tagging Docker Container ==="
docker build -t "${IMAGE_TAG}" .

echo "=== 3. Pushing Docker Container to GCR ==="
docker push "${IMAGE_TAG}"

echo "=== 4. Deploying to GCP Cloud Run ==="
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE_TAG}" \
  --platform managed \
  --region "${GCP_REGION}" \
  --project "${GCP_PROJECT}" \
  --allow-unauthenticated \
  --set-env-vars="COURTOS_MODE=real,COURTOS_DB_BACKEND=postgres,COURTOS_LOG_LEVEL=info" \
  --set-secrets="COURTOS_DB_URL=COURTOS_DB_URL:latest"

echo "=== Deployment Completed Successfully ==="
