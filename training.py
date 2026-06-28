import json
import os
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from dotenv import load_dotenv
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier


load_dotenv()

DATA_PATH = Path(os.getenv("WEEK2_DATA_PATH", "data/iris.csv"))
ARTIFACT_DIR = Path(os.getenv("WEEK2_ARTIFACT_DIR", "artifacts"))
MODEL_NAME = os.getenv("WEEK2_MODEL_NAME", "week2-dvc-model")
MAX_DEPTH = int(os.getenv("WEEK2_MAX_DEPTH", "2"))
RANDOM_STATE = int(os.getenv("WEEK2_RANDOM_STATE", "2"))
TEST_SIZE = float(os.getenv("WEEK2_TEST_SIZE", "0.4"))

MODEL_OUTPUT = Path("models/model.joblib")
METRICS_OUTPUT = Path("metrics/metrics.json")
FEATURE_COLUMNS = ["sepal_length", "sepal_width", "petal_length", "petal_width"]
TARGET_COLUMN = "species"


def now_timestamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def validate_columns(df, source):
    required_columns = [*FEATURE_COLUMNS, TARGET_COLUMN]
    missing_columns = [column for column in required_columns if column not in df.columns]
    if missing_columns:
        raise ValueError(f"{source} is missing required columns: {missing_columns}")


def build_metrics(y_true, predictions):
    return {
        "accuracy": float(accuracy_score(y_true, predictions)),
        "precision_weighted": float(precision_score(y_true, predictions, average="weighted", zero_division=0)),
        "recall_weighted": float(recall_score(y_true, predictions, average="weighted", zero_division=0)),
        "f1_weighted": float(f1_score(y_true, predictions, average="weighted", zero_division=0)),
    }


def train_model():
    dataset = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
    validate_columns(dataset, DATA_PATH)

    train_df, eval_df = train_test_split(
        dataset,
        test_size=TEST_SIZE,
        stratify=dataset[TARGET_COLUMN],
        random_state=RANDOM_STATE,
    )

    model = DecisionTreeClassifier(max_depth=MAX_DEPTH, random_state=RANDOM_STATE)
    model.fit(train_df[FEATURE_COLUMNS], train_df[TARGET_COLUMN])

    predictions = model.predict(eval_df[FEATURE_COLUMNS])
    metrics = build_metrics(eval_df[TARGET_COLUMN], predictions)

    run_id = "training-" + now_timestamp()
    run_dir = ARTIFACT_DIR / MODEL_NAME / run_id
    run_model_path = run_dir / "model" / "model.joblib"
    run_metrics_path = run_dir / "logs" / "training_metrics.json"
    prediction_path = run_dir / "logs" / "evaluation_predictions.csv"

    run_model_path.parent.mkdir(parents=True, exist_ok=True)
    prediction_path.parent.mkdir(parents=True, exist_ok=True)
    MODEL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    joblib.dump(model, run_model_path)
    joblib.dump(model, MODEL_OUTPUT)

    prediction_log = pd.DataFrame({
        "true_label": eval_df[TARGET_COLUMN].to_numpy(),
        "predicted_label": predictions,
    })
    prediction_log.to_csv(prediction_path, index=False)

    metrics_payload = {
        "model_name": MODEL_NAME,
        "run_id": run_id,
        "dataset_path": str(DATA_PATH),
        "samples": {
            "total": int(len(dataset)),
            "train": int(len(train_df)),
            "eval": int(len(eval_df)),
        },
        "hyperparameters": {
            "max_depth": MAX_DEPTH,
            "random_state": RANDOM_STATE,
            "test_size": TEST_SIZE,
        },
        "metrics": metrics,
        "artifact_path": str(run_dir),
        "model_path": str(MODEL_OUTPUT),
    }

    write_json(run_metrics_path, metrics_payload)
    write_json(METRICS_OUTPUT, metrics_payload)

    print(json.dumps(metrics_payload, indent=2))
    return metrics_payload


if __name__ == "__main__":
    train_model()
