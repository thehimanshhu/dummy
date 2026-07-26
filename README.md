# Week 6: Iris API Continuous Deployment

This assignment packages an Iris inference API as a Docker image, pushes the image to Google Artifact Registry, and deploys it to Google Kubernetes Engine through GitHub Actions.

## Files

```text
app/main.py                    FastAPI health and prediction endpoints
tests/test_api.py              API validation and prediction tests
models/model.joblib.dvc        DVC pointer for the validated Iris model
Dockerfile                     Production container image definition
k8s/deployment.yaml            Two-replica GKE Deployment
k8s/service.yaml               Public LoadBalancer Service
.github/workflows/week6-cd.yml Test, build, push, and deploy workflow
scripts/setup_gcp.sh            Artifact Registry, GKE, service account, and WIF setup
```

## Local Run

Create and activate the virtual environment:

```bash
cd week6-v1
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

Restore the model and run the tests:

```bash
dvc pull models/model.joblib.dvc
pytest -q
```

Start the API:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Test it from another terminal:

```bash
curl http://127.0.0.1:8080/health

curl -X POST http://127.0.0.1:8080/predict \
  -H "Content-Type: application/json" \
  -d '{
    "sepal_length": 5.1,
    "sepal_width": 3.5,
    "petal_length": 1.4,
    "petal_width": 0.2
  }'
```

Interactive API documentation is available at `http://127.0.0.1:8080/docs`.

## GCP Setup

Run these commands in Cloud Shell from the repository root:

```bash
export PROJECT_ID=<your-gcp-project-id>
export GITHUB_REPOSITORY=<github-owner>/<repository-name>

chmod +x scripts/setup_gcp.sh
./scripts/setup_gcp.sh
```

The script creates:

```text
Artifact Registry repository: iris-mlops
GKE cluster: iris-mlops-cluster
GCP service account: github-actions-week6
Workload Identity pool: github-pool-week6
Workload Identity provider: github-provider-week6
```

Add the three values printed by the script as GitHub repository secrets:

```text
GCP_PROJECT_ID
GCP_SERVICE_ACCOUNT
GCP_WORKLOAD_IDENTITY_PROVIDER
```

No service-account JSON key is required.

## Continuous Deployment

The workflow runs API tests for pull requests and pushes targeting `week_6`. A push to `week_6` continues with:

```text
1. Authenticate to GCP using Workload Identity Federation
2. Restore models/model.joblib from the DVC GCS remote
3. Build and tag the Docker image
4. Push commit and latest tags to Artifact Registry
5. Connect to the GKE cluster
6. Apply the Kubernetes Deployment and Service
7. Wait for the Deployment rollout to complete
```

## Verify GKE Deployment

After the workflow succeeds, run:

```bash
gcloud container clusters get-credentials iris-mlops-cluster \
  --zone us-central1-a \
  --project "$PROJECT_ID"

kubectl get deployment iris-api
kubectl get pods -l app=iris-api
kubectl get service iris-api
```

Wait until `EXTERNAL-IP` has a value:

```bash
export IRIS_API_IP=$(kubectl get service iris-api \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

curl "http://${IRIS_API_IP}/health"

curl -X POST "http://${IRIS_API_IP}/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "sepal_length": 6.4,
    "sepal_width": 3.2,
    "petal_length": 4.5,
    "petal_width": 1.5
  }'
```

## Pod and Container

A Docker container is a running instance of the Iris API image. It contains the application, Python dependencies, and trained model.

A Kubernetes Pod is the smallest unit Kubernetes deploys. Each Iris API Pod wraps one API container and provides its Kubernetes networking, health checks, and lifecycle. Kubernetes manages Pods instead of individual containers so it can restart failed workloads, replace replicas during updates, and group tightly coupled containers when needed.

## Objective Coverage

```text
Task 1: Pod and container explanation in this README and screencast
Task 2: FastAPI application and Dockerfile
Task 3: GCP service account and Workload Identity setup script
Task 4: GitHub Actions build and Artifact Registry push
Task 5: GKE Deployment, LoadBalancer Service, and API verification
Task 6: MLflow model retrieval is optional and is not used in this version
```

Delete the GKE cluster after the demonstration to stop cluster charges:

```bash
gcloud container clusters delete iris-mlops-cluster \
  --zone us-central1-a \
  --project "$PROJECT_ID"
```
