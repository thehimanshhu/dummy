#!/usr/bin/env bash
set -euo pipefail

# Update these values if your project or repository changes.
PROJECT_ID="${PROJECT_ID:-project-5af14217-0027-40e0-873}"
SA_NAME="${SA_NAME:-github-actions-mlops}"
POOL_ID="${POOL_ID:-github-pool}"
PROVIDER_ID="${PROVIDER_ID:-github-provider}"
GITHUB_REPO="${GITHUB_REPO:-thehimanshhu/dummy}"

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
MEMBER="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${GITHUB_REPO}"
PROVIDER_RESOURCE="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"

echo "Project: $PROJECT_ID"
echo "Project number: $PROJECT_NUMBER"
echo "Service account: $SA_EMAIL"
echo "GitHub repo: $GITHUB_REPO"
echo "WIF member: $MEMBER"
echo "WIF provider: $PROVIDER_RESOURCE"

gcloud config set project "$PROJECT_ID"

echo "Enabling required APIs..."
gcloud services enable iamcredentials.googleapis.com --project="$PROJECT_ID"
gcloud services enable bigquerystorage.googleapis.com --project="$PROJECT_ID"

echo "Creating service account if needed..."
if gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" >/dev/null 2>&1; then
  echo "Service account already exists: $SA_EMAIL"
else
  gcloud iam service-accounts create "$SA_NAME" \
    --project="$PROJECT_ID" \
    --display-name="GitHub Actions MLOps CI"
fi

echo "Granting project roles to service account..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/storage.objectViewer"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/bigquery.jobUser"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/bigquery.readSessionUser"

echo "Creating Workload Identity Pool if needed..."
if gcloud iam workload-identity-pools describe "$POOL_ID" \
  --project="$PROJECT_ID" \
  --location="global" >/dev/null 2>&1; then
  echo "Workload Identity Pool already exists: $POOL_ID"
else
  gcloud iam workload-identity-pools create "$POOL_ID" \
    --project="$PROJECT_ID" \
    --location="global" \
    --display-name="GitHub Actions Pool"
fi

echo "Creating OIDC provider if needed..."
if gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_ID" >/dev/null 2>&1; then
  echo "OIDC provider already exists: $PROVIDER_ID"
else
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
    --project="$PROJECT_ID" \
    --location="global" \
    --workload-identity-pool="$POOL_ID" \
    --display-name="GitHub Actions Provider" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
    --attribute-condition="assertion.repository=='${GITHUB_REPO}'"
fi

echo "Granting GitHub repo permission to impersonate service account..."
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="$MEMBER"

gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --project="$PROJECT_ID" \
  --role="roles/iam.serviceAccountTokenCreator" \
  --member="$MEMBER"

echo
echo "Service account IAM policy:"
gcloud iam service-accounts get-iam-policy "$SA_EMAIL" --project="$PROJECT_ID"

echo
echo "Add these GitHub repository secrets:"
echo "GCP_WORKLOAD_IDENTITY_PROVIDER=$PROVIDER_RESOURCE"
echo "GCP_SERVICE_ACCOUNT=$SA_EMAIL"
echo "GCP_PROJECT_ID=$PROJECT_ID"

echo
echo "Done."
