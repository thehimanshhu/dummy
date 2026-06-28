# Week 2 V3: DVC Versioning for Iris Training

This folder contains a Week 2 DVC workflow for the Iris classifier. Git stores the code and DVC pointer files, while DVC stores the dataset and model contents in a Google Cloud Storage remote.

The workflow creates two reproducible versions:

- Dataset version 1 with its trained model
- Dataset version 2 with its trained model

The default model name used by the script is:

```text
week2-dvc-model
```

## Files

```text
training.py               Iris training script
requirements.txt          Python dependencies
data/v1/data.csv          First dataset version
data/v2/data.csv          Second dataset version
.gitignore                Local/generated files excluded from Git
README.md                 Assignment workflow summary
commands.md               Full local and Cloud Shell command sequences
```

## Cloud Shell Setup

Set the project and bucket values:

```bash
PROJECT_ID=<your-project-id>
BUCKET=mlops-course-${PROJECT_ID}-unique
LOCATION=us-central1
```

Create the Python environment:

```bash
cd week-2

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
pip install dvc dvc-gs
```

## Initialize Git and DVC

```bash
git init
git checkout -b week_2

dvc init

git add .dvc .dvcignore .gitignore README.md requirements.txt training.py
git commit -m "Initialize DVC training workflow"
```

## Configure GCS DVC Remote

```bash
gcloud config set project $PROJECT_ID

gcloud storage buckets describe gs://$BUCKET || \
gcloud storage buckets create gs://$BUCKET --project=$PROJECT_ID --location=$LOCATION

dvc remote add -d gcsremote gs://$BUCKET/week_2/dvc-store

git add .dvc/config
git commit -m "Add GCS remote for DVC"
```

## Version 1

Track the first dataset version:

```bash
cp data/v1/data.csv data/iris.csv

dvc add data/iris.csv

git add data/iris.csv.dvc data/.gitignore
git commit -m "Track first Iris dataset version"

dvc push
```

Train the first model:

```bash
export WEEK2_DATA_PATH=data/iris.csv
export WEEK2_ARTIFACT_DIR=artifacts
export WEEK2_MODEL_NAME=week2-dvc-model

python training.py
```

Track the first model artifact:

```bash
dvc add models/model.joblib

git add models/model.joblib.dvc metrics/metrics.json
git commit -m "Track model trained with first dataset"

dvc push

git tag -a v1.0 -m "Week 2 V3 data and model version 1"
```

## Version 2

Track the second dataset version:

```bash
cp data/v2/data.csv data/iris.csv

dvc add data/iris.csv

git add data/iris.csv.dvc
git commit -m "Track second Iris dataset version"

dvc push
```

Train the second model:

```bash
python training.py
```

Track the second model artifact:

```bash
dvc add models/model.joblib

git add models/model.joblib.dvc metrics/metrics.json
git commit -m "Track model trained with second dataset"

dvc push

git tag -a v2.0 -m "Week 2 V3 data and model version 2"
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

Return to the branch:

```bash
git checkout week_2
dvc checkout
```

## Final Push

```bash
git push origin week_2
git push origin v1.0 v2.0
```

Git should include:

```text
README.md
requirements.txt
training.py
.gitignore
.dvc/config
.dvcignore
data/iris.csv.dvc
models/model.joblib.dvc
metrics/metrics.json
```

Git should not include:

```text
.dvc/cache/
.venv/
data/iris.csv
models/model.joblib
artifacts/
tmp/
split/
```
