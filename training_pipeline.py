import json
import os
import shlex
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from dotenv import load_dotenv
from sklearn import metrics
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier


load_dotenv()

PROJECT_ID = os.getenv("PROJECT_ID", "myprojectid")
LOCATION = os.getenv("LOCATION", "us-central1")
BUCKET_NAME = os.getenv("BUCKET_NAME") or f"mlops-course-{PROJECT_ID}-unique"
BUCKET_URI = f"gs://{BUCKET_NAME}"

MODEL_NAME = os.getenv("MODEL_NAME", "week-2-model")
USE_GCS = os.getenv("USE_GCS", "false").lower() == "true"
RAW_DATA_PATH = os.getenv("RAW_DATA_PATH", "data/iris.csv")
TRAIN_DATA_URI = os.getenv("TRAIN_DATA_URI") or ("split/train.csv" if not USE_GCS else f"{BUCKET_URI}/week_2/data/train.csv")
EVAL_DATA_URI = os.getenv("EVAL_DATA_URI") or ("split/test.csv" if not USE_GCS else f"{BUCKET_URI}/week_2/data/test.csv")
ARTIFACT_ROOT = os.getenv("ARTIFACT_ROOT") or ("artifacts" if not USE_GCS else f"{BUCKET_URI}/week_2/artifacts")

MAX_DEPTH = int(os.getenv("MAX_DEPTH", "2"))
RANDOM_STATE = int(os.getenv("RANDOM_STATE", "2"))

FEATURE_COLUMNS = ["sepal_length", "sepal_width", "petal_length", "petal_width"]
TARGET_COLUMN = "species"


def now_timestamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def is_gcs_uri(uri):
    return str(uri).startswith("gs://")


def run_command(command):
    result = subprocess.run(command, shell=True)
    return result.returncode


def storage_cp(source, destination):
    command = f"gcloud storage cp {shlex.quote(str(source))} {shlex.quote(str(destination))}"
    status = run_command(command)
    if status != 0:
        raise RuntimeError(f"Command failed: {command}")


def gcs_object_exists(uri):
    if not is_gcs_uri(uri):
        return Path(uri).exists()
    command = f"gcloud storage ls {shlex.quote(str(uri))} >/dev/null 2>&1"
    return run_command(command) == 0


def upload_file_if_missing(local_path, destination_uri):
    if gcs_object_exists(destination_uri):
        print(f"Already exists, skipping upload: {destination_uri}")
        return destination_uri
    return upload_file(local_path, destination_uri)


def download_uri(uri, local_path):
    local_path = Path(local_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    if is_gcs_uri(uri):
        storage_cp(uri, local_path)
    else:
        shutil.copyfile(Path(uri), local_path)
    return local_path


def upload_file(local_path, destination_uri):
    local_path = Path(local_path)
    if is_gcs_uri(destination_uri):
        storage_cp(local_path, destination_uri)
    else:
        destination = Path(destination_uri)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if local_path.resolve() != destination.resolve():
            shutil.copyfile(local_path, destination)
        else:
            print(f"Already in place, skipping copy: {destination}")
    return destination_uri


def join_uri(base_uri, *parts):
    return "/".join([str(base_uri).rstrip("/"), *[str(part).strip("/") for part in parts if part]])


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def validate_columns(df, source):
    required = [*FEATURE_COLUMNS, TARGET_COLUMN]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"{source} is missing required columns: {missing}")


def classification_metrics(y_true, predictions):
    return {
        "accuracy": float(metrics.accuracy_score(y_true, predictions)),
        "precision_weighted": float(metrics.precision_score(y_true, predictions, average="weighted", zero_division=0)),
        "recall_weighted": float(metrics.recall_score(y_true, predictions, average="weighted", zero_division=0)),
        "f1_weighted": float(metrics.f1_score(y_true, predictions, average="weighted", zero_division=0)),
    }


def ensure_bucket():
    if not is_gcs_uri(BUCKET_URI):
        return
    status = run_command(f"gcloud storage buckets describe {shlex.quote(BUCKET_URI)} >/dev/null 2>&1")
    if status == 0:
        print(f"Bucket already exists: {BUCKET_URI}")
        return
    create_status = run_command(
        f"gcloud storage buckets create {shlex.quote(BUCKET_URI)} "
        f"--project={shlex.quote(PROJECT_ID)} --location={shlex.quote(LOCATION)} >/dev/null 2>&1"
    )
    if create_status != 0:
        raise RuntimeError(
            f"Could not create bucket {BUCKET_URI}. Create it manually or use an account "
            "with storage.buckets.create permission."
        )
    print(f"Created bucket: {BUCKET_URI}")


def prepare_train_eval_data(raw_data_path=RAW_DATA_PATH, upload_to_gcs=USE_GCS):
    raw_df = pd.read_csv(raw_data_path, encoding="utf-8-sig")
    validate_columns(raw_df, raw_data_path)

    train_df, eval_df = train_test_split(
        raw_df,
        test_size=0.4,
        stratify=raw_df[TARGET_COLUMN],
        random_state=42,
    )

    split_dir = Path("split")
    split_dir.mkdir(parents=True, exist_ok=True)
    train_path = split_dir / "train.csv"
    eval_path = split_dir / "test.csv"
    train_df.to_csv(train_path, index=False)
    eval_df.to_csv(eval_path, index=False)

    train_uri = str(train_path)
    eval_uri = str(eval_path)

    if upload_to_gcs:
        train_uri = TRAIN_DATA_URI
        eval_uri = EVAL_DATA_URI
        upload_file_if_missing(train_path, TRAIN_DATA_URI)
        upload_file_if_missing(eval_path, EVAL_DATA_URI)

    return {
        "train_uri": train_uri,
        "eval_uri": eval_uri,
        "train_rows": len(train_df),
        "eval_rows": len(eval_df),
    }


def train_pipeline(train_data_uri, eval_data_uri, artifact_root, model_name=MODEL_NAME, random_state=RANDOM_STATE):
    run_timestamp = "training-" + now_timestamp()
    tmp_dir = Path("tmp") / run_timestamp
    artifact_uri = join_uri(artifact_root, model_name, run_timestamp)

    train_local_path = download_uri(train_data_uri, tmp_dir / "train.csv")
    eval_local_path = download_uri(eval_data_uri, tmp_dir / "eval.csv")

    train_df = pd.read_csv(train_local_path, encoding="utf-8-sig")
    eval_df = pd.read_csv(eval_local_path, encoding="utf-8-sig")
    validate_columns(train_df, train_data_uri)
    validate_columns(eval_df, eval_data_uri)

    x_train = train_df[FEATURE_COLUMNS]
    y_train = train_df[TARGET_COLUMN]
    x_eval = eval_df[FEATURE_COLUMNS]
    y_eval = eval_df[TARGET_COLUMN]

    model = DecisionTreeClassifier(max_depth=MAX_DEPTH, random_state=random_state)
    model.fit(x_train, y_train)

    predictions = model.predict(x_eval)
    probabilities = model.predict_proba(x_eval)
    run_metrics = classification_metrics(y_eval, predictions)

    local_artifact_dir = Path("artifacts") / model_name / run_timestamp
    model_path = local_artifact_dir / "model" / "model.joblib"
    logs_dir = local_artifact_dir / "logs"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(model, model_path)

    prediction_log = pd.DataFrame({
        "true_label": y_eval.to_numpy(),
        "predicted_label": predictions,
        "confidence": probabilities.max(axis=1),
    })
    prediction_path = logs_dir / "evaluation_predictions.csv"
    prediction_log.to_csv(prediction_path, index=False)

    feature_stats_path = logs_dir / "feature_stats.json"
    write_json(feature_stats_path, {
        "train": x_train.describe().to_dict(),
        "eval": x_eval.describe().to_dict(),
        "train_missing_values": x_train.isna().sum().to_dict(),
        "eval_missing_values": x_eval.isna().sum().to_dict(),
    })

    metrics_path = logs_dir / "training_metrics.json"
    write_json(metrics_path, {
        "model_name": model_name,
        "run_timestamp": run_timestamp,
        "dataset": {"train_data_uri": train_data_uri, "eval_data_uri": eval_data_uri},
        "samples": {"train": int(len(train_df)), "eval": int(len(eval_df))},
        "hyperparameters": {"max_depth": MAX_DEPTH, "random_state": random_state},
        "metrics": run_metrics,
        "artifact_uri": artifact_uri,
    })

    metadata = {
        "model_name": model_name,
        "run_timestamp": run_timestamp,
        "framework": "scikit-learn",
        "task": "iris_classification",
        "artifact_uri": artifact_uri,
        "model_uri": join_uri(artifact_uri, "model", "model.joblib"),
        "eval_data_uri": eval_data_uri,
    }
    metadata_path = local_artifact_dir / "metadata.json"
    write_json(metadata_path, metadata)

    upload_file(model_path, join_uri(artifact_uri, "model", "model.joblib"))
    upload_file(prediction_path, join_uri(artifact_uri, "logs", "evaluation_predictions.csv"))
    upload_file(feature_stats_path, join_uri(artifact_uri, "logs", "feature_stats.json"))
    upload_file(metrics_path, join_uri(artifact_uri, "logs", "training_metrics.json"))
    upload_file(metadata_path, join_uri(artifact_uri, "metadata.json"))

    result = {**metadata, "metrics": run_metrics}
    print(json.dumps(result, indent=2))
    return result


def main():
    print(json.dumps({
        "project_id": PROJECT_ID,
        "bucket_uri": BUCKET_URI,
        "use_gcs": USE_GCS,
        "raw_data_path": RAW_DATA_PATH,
        "train_data_uri": TRAIN_DATA_URI,
        "eval_data_uri": EVAL_DATA_URI,
        "artifact_root": ARTIFACT_ROOT,
    }, indent=2))

    if USE_GCS:
        ensure_bucket()

    split_data = prepare_train_eval_data(upload_to_gcs=USE_GCS)
    print(json.dumps(split_data, indent=2))

    training_runs = [
        train_pipeline(split_data["train_uri"], split_data["eval_uri"], ARTIFACT_ROOT, random_state=RANDOM_STATE)
    ]

    training_runs_path = Path("artifacts") / "training_runs.json"
    write_json(training_runs_path, training_runs)
    if is_gcs_uri(ARTIFACT_ROOT):
        upload_file(training_runs_path, join_uri(ARTIFACT_ROOT, MODEL_NAME, "training_runs.json"))

    print(pd.DataFrame([
        {
            "run_timestamp": run["run_timestamp"],
            "artifact_uri": run["artifact_uri"],
            "model_uri": run["model_uri"],
            "eval_data_uri": run["eval_data_uri"],
            "accuracy": run["metrics"]["accuracy"],
        }
        for run in training_runs
    ]))


if __name__ == "__main__":
    main()
