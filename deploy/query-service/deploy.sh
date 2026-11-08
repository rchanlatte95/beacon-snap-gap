#!/bin/sh
# Deploy script for QueryService on Cloud Run (REQ-38, REQ-43, REQ-46, REQ-49, REQ-50, REQ-52, Z-8, Z-13, Z-14, Z-19)
# Strict error handling: fail fast and loud if any command fails or variables are unset (CL9).
set -eu

# -----------------------------------------------------------------------------
# Configuration Variables (Required from environment or Operator defaults)
# -----------------------------------------------------------------------------
# GCP Project ID hosting Cloud Run and Cloud Storage bucket (Z-14: <gcp-project>)
PROJECT="${PROJECT:-<gcp-project>}"

# GCP Region for Cloud Run service and Vertex AI (Z-8, Z-4: us-east1)
REGION="${REGION:-us-east1}"

# Cloud Run Service Name
SERVICE="${SERVICE:-query-service}"

# Destination Container Image Tag in Artifact Registry
IMAGE="${IMAGE:-${REGION}-docker.pkg.dev/${PROJECT}/cloud-run-source-deploy/${SERVICE}:latest}"

# Dedicated Cloud Run Service Account (REQ-52: using service's own identity)
# Operator must provision this service account prior to deployment.
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-query-service-sa@${PROJECT}.iam.gserviceaccount.com}"

# Vertex AI Gemini model identifier (Z-8: Gemini 3.8 Flash to start, named in configuration).
# No default: the Operator sets the exact Vertex model ID after checking it answers in the project.
MODEL="${MODEL:-}"

# Google Cloud Storage bucket holding canonical warehouse (Z-14, REQ-46: <warehouse-bucket>)
BUCKET="${BUCKET:-<warehouse-bucket>}"

# Read-only GCS volume mount path inside container (REQ-52, Z-19 option A)
MOUNT_PATH="${MOUNT_PATH:-/mnt/warehouse}"

# -----------------------------------------------------------------------------
# Validate Required Variables (Fail loud if empty string is supplied)
# -----------------------------------------------------------------------------
if [ -z "${PROJECT}" ]; then
  echo "ERROR: PROJECT is required and cannot be empty." >&2
  exit 1
fi

if [ -z "${REGION}" ]; then
  echo "ERROR: REGION is required and cannot be empty." >&2
  exit 1
fi

if [ -z "${SERVICE}" ]; then
  echo "ERROR: SERVICE is required and cannot be empty." >&2
  exit 1
fi

if [ -z "${IMAGE}" ]; then
  echo "ERROR: IMAGE is required and cannot be empty." >&2
  exit 1
fi

if [ -z "${SERVICE_ACCOUNT}" ]; then
  echo "ERROR: SERVICE_ACCOUNT is required and cannot be empty." >&2
  exit 1
fi

if [ -z "${MODEL}" ]; then
  echo "ERROR: MODEL is required and cannot be empty." >&2
  exit 1
fi

if [ -z "${BUCKET}" ]; then
  echo "ERROR: BUCKET is required and cannot be empty." >&2
  exit 1
fi

if [ -z "${MOUNT_PATH}" ]; then
  echo "ERROR: MOUNT_PATH is required and cannot be empty." >&2
  exit 1
fi

# -----------------------------------------------------------------------------
# IAM Roles Documentation (Informational only - do NOT grant automatically):
#
# The dedicated service account (${SERVICE_ACCOUNT}) requires the following
# least-privilege IAM bindings:
#
# 1. Vertex AI User (for Gemini model invocations):
#    gcloud projects add-iam-policy-binding "${PROJECT}" \
#      --member="serviceAccount:${SERVICE_ACCOUNT}" \
#      --role="roles/aiplatform.user"
#
# 2. Storage Object Viewer (for read-only warehouse volume mount from bucket):
#    gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
#      --member="serviceAccount:${SERVICE_ACCOUNT}" \
#      --role="roles/storage.objectViewer"
# -----------------------------------------------------------------------------

# Locate repository root relative to this script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

echo "=== Deploying QueryService to Cloud Run ==="
echo "Project:         ${PROJECT}"
echo "Region:          ${REGION}"
echo "Service:         ${SERVICE}"
echo "Image:           ${IMAGE}"
echo "Service Account: ${SERVICE_ACCOUNT}"
echo "Model:           ${MODEL}"
echo "Bucket:          ${BUCKET}"
echo "Mount Path:      ${MOUNT_PATH}"
echo "Repository Root: ${REPO_ROOT}"
echo "=========================================="

# Build and submit the container image to Google Cloud Artifact Registry
echo "--> Building container image via Google Cloud Build..."
gcloud builds submit "${REPO_ROOT}" \
  --project="${PROJECT}" \
  --config=/dev/null \
  --tag="${IMAGE}" \
  --file="${SCRIPT_DIR}/Dockerfile"

# Deploy container image to Cloud Run with internal-only ingress and read-only GCS volume mount
echo "--> Deploying service to Cloud Run..."
gcloud run deploy "${SERVICE}" \
  --project="${PROJECT}" \
  --region="${REGION}" \
  --image="${IMAGE}" \
  --ingress=internal \
  --no-allow-unauthenticated \
  --service-account="${SERVICE_ACCOUNT}" \
  --add-volume="name=warehouse,type=cloud-storage,bucket=${BUCKET},readonly=true" \
  --add-volume-mount="volume=warehouse,mount-path=${MOUNT_PATH}" \
  --set-env-vars="WAREHOUSE_LOCATION=${MOUNT_PATH},QUERY_SERVICE_MODEL=${MODEL},GOOGLE_CLOUD_PROJECT=${PROJECT},GOOGLE_CLOUD_LOCATION=${REGION}"

echo "=== QueryService deployment completed successfully ==="
