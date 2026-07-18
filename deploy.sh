#!/usr/bin/env bash
set -eo pipefail

# Configuration with environment defaults
GCP_PROJECT="${GCP_PROJECT:-courtos-production}"
GCP_REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="courtos-api"
REPOSITORY_NAME="${REPOSITORY_NAME:-courtos-repo}"
IMAGE_TAG="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT}/${REPOSITORY_NAME}/${SERVICE_NAME}:latest"

echo "=== 1. Building Container via Docker (Multi-Stage Build) ==="
docker build -t "${IMAGE_TAG}" .

echo "=== 2. Pushing Container to Artifact Registry ==="
gcloud auth configure-docker "${GCP_REGION}-docker.pkg.dev" --quiet
docker push "${IMAGE_TAG}"

echo "=== 3. Deploying to GCP Cloud Run ==="
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE_TAG}" \
  --platform managed \
  --region "${GCP_REGION}" \
  --project "${GCP_PROJECT}" \
  --port 8080 \
  --allow-unauthenticated \
  --no-cpu-throttling \
  --concurrency 80 \
  --set-env-vars="COURTOS_MODE=real,COURTOS_DB_BACKEND=postgres,COURTOS_LOG_LEVEL=info" \
  --set-secrets="COURTOS_DB_URL=COURTOS_DB_URL:latest"

echo "=== Deployment Completed Successfully ==="

