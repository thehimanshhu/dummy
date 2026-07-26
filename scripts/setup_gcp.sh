#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID before running this script.}"
: "${GITHUB_REPOSITORY:?Set GITHUB_REPOSITORY as owner/repository.}"

GAR_LOCATION="${GAR_LOCATION:-us-central1}"
GAR_REPOSITORY="${GAR_REPOSITORY:-iris-mlops}"
GKE_CLUSTER="${GKE_CLUSTER:-iris-mlops-cluster}"
GKE_ZONE="${GKE_ZONE:-us-central1-a}"
SERVICE_ACCOUNT_ID="${SERVICE_ACCOUNT_ID:-github-actions-week6}"
WIF_POOL_ID="${WIF_POOL_ID:-github-pool-week6}"
WIF_PROVIDER_ID="${WIF_PROVIDER_ID:-github-provider-week6}"

wait_for_service_account() {
  local attempt

  for attempt in {1..12}; do
    if gcloud iam service-accounts describe "${SERVICE_ACCOUNT}" \
      --project="${PROJECT_ID}" >/dev/null 2>&1; then
      return 0
    fi
    printf 'Waiting for service account IAM propagation (%s/12)...\n' "${attempt}"
    sleep 5
  done

  printf 'Service account did not become available: %s\n' "${SERVICE_ACCOUNT}" >&2
  return 1
}

add_project_role() {
  local role="$1"
  local attempt

  for attempt in {1..6}; do
    if gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
      --member="serviceAccount:${SERVICE_ACCOUNT}" \
      --role="${role}" \
      --quiet; then
      return 0
    fi
    printf 'Retrying IAM role %s (%s/6)...\n' "${role}" "${attempt}"
    sleep 10
  done

  printf 'Could not grant IAM role: %s\n' "${role}" >&2
  return 1
}

gcloud config set project "${PROJECT_ID}"
gcloud services enable \
  artifactregistry.googleapis.com \
  container.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT_ID}@${PROJECT_ID}.iam.gserviceaccount.com"

if ! gcloud artifacts repositories describe "${GAR_REPOSITORY}" \
  --location="${GAR_LOCATION}" >/dev/null 2>&1; then
  gcloud artifacts repositories create "${GAR_REPOSITORY}" \
    --repository-format=docker \
    --location="${GAR_LOCATION}" \
    --description="Iris inference API images"
fi

if ! gcloud container clusters describe "${GKE_CLUSTER}" \
  --zone="${GKE_ZONE}" >/dev/null 2>&1; then
  gcloud container clusters create "${GKE_CLUSTER}" \
    --zone="${GKE_ZONE}" \
    --machine-type=e2-standard-2 \
    --disk-type=pd-standard \
    --disk-size=30 \
    --num-nodes=1 \
    --release-channel=regular
fi

if ! gcloud iam service-accounts describe "${SERVICE_ACCOUNT}" \
  --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${SERVICE_ACCOUNT_ID}" \
    --project="${PROJECT_ID}" \
    --display-name="GitHub Actions Week 6 CD"
fi

wait_for_service_account

for role in \
  roles/artifactregistry.writer \
  roles/container.developer \
  roles/storage.objectViewer; do
  add_project_role "${role}"
done

NODE_SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${NODE_SERVICE_ACCOUNT}" \
  --role="roles/artifactregistry.reader" \
  --quiet

if ! gcloud iam workload-identity-pools describe "${WIF_POOL_ID}" \
  --location=global >/dev/null 2>&1; then
  gcloud iam workload-identity-pools create "${WIF_POOL_ID}" \
    --location=global \
    --display-name="GitHub Actions Week 6"
fi

if ! gcloud iam workload-identity-pools providers describe "${WIF_PROVIDER_ID}" \
  --location=global \
  --workload-identity-pool="${WIF_POOL_ID}" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers create-oidc "${WIF_PROVIDER_ID}" \
    --location=global \
    --workload-identity-pool="${WIF_POOL_ID}" \
    --display-name="GitHub Actions Week 6 Provider" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
    --attribute-condition="assertion.repository=='${GITHUB_REPOSITORY}'"
fi

WIF_MEMBER="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL_ID}/attribute.repository/${GITHUB_REPOSITORY}"

for role in \
  roles/iam.workloadIdentityUser \
  roles/iam.serviceAccountTokenCreator; do
  gcloud iam service-accounts add-iam-policy-binding "${SERVICE_ACCOUNT}" \
    --role="${role}" \
    --member="${WIF_MEMBER}" \
    --quiet
done

WIF_PROVIDER="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL_ID}/providers/${WIF_PROVIDER_ID}"

printf '\nCreate these GitHub repository secrets:\n'
printf 'GCP_PROJECT_ID=%s\n' "${PROJECT_ID}"
printf 'GCP_SERVICE_ACCOUNT=%s\n' "${SERVICE_ACCOUNT}"
printf 'GCP_WORKLOAD_IDENTITY_PROVIDER=%s\n' "${WIF_PROVIDER}"
