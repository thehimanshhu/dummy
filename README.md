# Week 4: Self-Contained Iris CI Pipeline

This folder contains the Week 4 CI assignment as a self-contained pipeline. It includes the DVC pointers for the Iris dataset/model, Feast feature definitions, pytest tests, CML report generation, and the GitHub Actions workflow.

No `week-2` or `week-3` folder is required at runtime.

## Files

```text
data/iris.csv.dvc                     DVC pointer for the Iris dataset
models/model.joblib.dvc               DVC pointer for the trained model
metrics/metrics.json                  Latest training metrics snapshot
feature_repo/feature_store.yaml       Feast config: BigQuery offline, SQLite online
feature_repo/iris_features.py         Feast entity/source/feature view definitions
tests/test_data_validation.py         Data validation tests
tests/test_model_evaluation.py        Model loading and quality tests
scripts/generate_cml_report.py        Basic model evaluation report
scripts/dvc_feast_validation_pipeline.py  Combined DVC + Feast validation report
.github/workflows/week4-ci.yml        GitHub Actions workflow
```

## Cloud Shell Run

From the repository root:

```bash
cd week4-v1

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
pip install pytest dvc dvc-gs google-cloud-bigquery 'feast[gcp]'
```

Set GCP values:

```bash
export PROJECT_ID=<your-project-id>
export BIGQUERY_DATASET=iris_feast_week4
export BIGQUERY_TABLE=iris_features
export BIGQUERY_LOCATION=US
export INFERENCE_SAMPLE_IDS=0,10,20

gcloud config set project $PROJECT_ID
```

Pull DVC data and model:

```bash
dvc pull
```

This restores:

```text
data/iris.csv
models/model.joblib
```

Run tests:

```bash
pytest tests
```

Generate the basic CML-style model report:

```bash
python scripts/generate_cml_report.py
```

Run the combined DVC + Feast validation:

```bash
python scripts/dvc_feast_validation_pipeline.py
```

Check generated reports:

```bash
ls -lh reports
cat reports/evaluation_report.md
cat reports/dvc_feast_validation_report.md
```

## Combined DVC + Feast Pipeline

The combined pipeline uses only files inside `week4-v1`:

```text
DVC data: data/iris.csv
DVC model: models/model.joblib
Feast repo: feature_repo/
BigQuery offline table: <PROJECT_ID>.iris_feast_week4.iris_features
SQLite online store: feature_repo/data/online_store.db
```

It performs:

```text
1. Load DVC-restored Iris data
2. Upload features to BigQuery
3. Apply Feast definitions
4. Materialize features into SQLite
5. Load the DVC-restored model
6. Fetch online features from Feast
7. Compare online predictions with raw feature predictions
8. Write a CML-ready Markdown report
```

## GitHub Actions

The workflow is:

```text
.github/workflows/week4-ci.yml
```

It runs on:

```text
push
pull_request
```

The workflow:

```text
1. Checks out the repository
2. Installs dependencies
3. Authenticates to Google Cloud
4. Runs dvc pull inside week4-v1
5. Runs pytest
6. Generates model evaluation reports
7. Runs combined DVC + Feast validation
8. Posts a CML report on pull requests
```

## GitHub Secrets

Configure these secrets:

```text
GCP_WORKLOAD_IDENTITY_PROVIDER
GCP_SERVICE_ACCOUNT
GCP_PROJECT_ID
```

`GCP_WORKLOAD_IDENTITY_PROVIDER` is the full Workload Identity provider resource name.

`GCP_SERVICE_ACCOUNT` is the service account email used by GitHub Actions.

`GCP_PROJECT_ID` is the project used for the BigQuery offline store.

No JSON service account key is required.

## Reports

Generated files:

```text
reports/pytest-output.txt
reports/pytest-results.xml
reports/evaluation_metrics.json
reports/evaluation_report.md
reports/dvc_feast_validation_metrics.json
reports/dvc_feast_validation_report.md
reports/dvc_feast_predictions.csv
reports/cml-report.md
```

Reports are generated artifacts and should not be committed.
