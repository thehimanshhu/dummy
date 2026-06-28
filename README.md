# Week 2: DVC Versioning for Iris Pipeline

This repository contains the Week 2 Iris pipeline work with Git, DVC, and a Google Cloud Storage DVC remote.

The workflow versions:

- Iris dataset version 1
- Model trained from dataset version 1
- Iris dataset version 2
- Model trained from dataset version 2

The large files are tracked through DVC. Git stores the code, README, DVC config, DVC pointer files, and metrics.

## Files

```text
training_pipeline.py      Training script for the Iris classifier
requirements.txt          Python dependencies
data/v1/data.csv          Dataset version 1 source file
data/v2/data.csv          Dataset version 2 source file
.gitignore                Files ignored from Git
README.md                 Assignment run steps
```

## Cloud Shell Commands

Set the project and bucket name:

```bash
PROJECT_ID=<your-project-id>
BUCKET=mlops-course-${PROJECT_ID}-unique
LOCATION=us-central1
```

Create and activate the environment:

```bash
cd week-2_v1

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
pip install dvc dvc-gs
```

Initialize Git and DVC:

```bash
git init
git checkout -b week_2

dvc init

git add .dvc .dvcignore .gitignore README.md requirements.txt training_pipeline.py
git commit -m "Initialize DVC for week 2"
```

Configure Google Cloud Storage as the DVC remote:

```bash
gcloud config set project $PROJECT_ID

gcloud storage buckets describe gs://$BUCKET || \
gcloud storage buckets create gs://$BUCKET --project=$PROJECT_ID --location=$LOCATION

dvc remote add -d gcsremote gs://$BUCKET/week_2/dvc-store

git add .dvc/config
git commit -m "Configure DVC GCS remote"
```

Verify the DVC remote:

```bash
dvc remote list
```

## Version 1

Track dataset version 1:

```bash
cp data/v1/data.csv data/iris.csv

dvc add data/iris.csv

git add data/iris.csv.dvc data/.gitignore
git commit -m "Track Iris data version 1"

dvc push
```

Train model version 1:

```bash
export USE_GCS=false
export RAW_DATA_PATH=data/iris.csv
export ARTIFACT_ROOT=artifacts
export MODEL_NAME=week-2-model

python training_pipeline.py
```

Track model version 1:

```bash
mkdir -p models metrics

LATEST_RUN=$(ls -td artifacts/week-2-model/training-* | head -1)

cp $LATEST_RUN/model/model.joblib models/model.joblib
cp $LATEST_RUN/logs/training_metrics.json metrics/metrics.json

dvc add models/model.joblib

git add models/model.joblib.dvc metrics/metrics.json
git commit -m "Track model version 1"

dvc push

git tag -a v1.0 -m "Iris data and model version 1"
```

## Version 2

Track dataset version 2:

```bash
cp data/v2/data.csv data/iris.csv

dvc add data/iris.csv

git add data/iris.csv.dvc
git commit -m "Track Iris data version 2"

dvc push
```

Train model version 2:

```bash
python training_pipeline.py
```

Track model version 2:

```bash
LATEST_RUN=$(ls -td artifacts/week-2-model/training-* | head -1)

cp $LATEST_RUN/model/model.joblib models/model.joblib
cp $LATEST_RUN/logs/training_metrics.json metrics/metrics.json

dvc add models/model.joblib

git add models/model.joblib.dvc metrics/metrics.json
git commit -m "Track model version 2"

dvc push

git tag -a v2.0 -m "Iris data and model version 2"
```

## Verify Version Switching

Switch to version 1:

```bash
git checkout v1.0
dvc checkout
wc -l data/iris.csv
ls -lh models/model.joblib
cat metrics/metrics.json
```

Switch to version 2:

```bash
git checkout v2.0
dvc checkout
wc -l data/iris.csv
ls -lh models/model.joblib
cat metrics/metrics.json
```

Return to the working branch:

```bash
git checkout week_2
dvc checkout
```

## Final Git Push

```bash
git push origin week_2
git push origin v1.0 v2.0
```

Git should contain:

```text
README.md
requirements.txt
training_pipeline.py
.gitignore
.dvc/config
.dvcignore
data/iris.csv.dvc
models/model.joblib.dvc
metrics/metrics.json
```

Git should not contain:

```text
.dvc/cache/
data/iris.csv
models/model.joblib
artifacts/
tmp/
split/
.venv/
```
