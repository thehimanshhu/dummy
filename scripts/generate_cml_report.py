import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn import metrics


REPO_ROOT = Path(__file__).resolve().parents[2]
WEEK4_DIR = REPO_ROOT / "week4-v1"
DATA_PATH = WEEK4_DIR / "data" / "iris.csv"
MODEL_PATH = WEEK4_DIR / "models" / "model.joblib"
REPORT_DIR = Path(__file__).resolve().parents[1] / "reports"
REPORT_PATH = REPORT_DIR / "evaluation_report.md"
METRICS_PATH = REPORT_DIR / "evaluation_metrics.json"

FEATURE_COLUMNS = ["sepal_length", "sepal_width", "petal_length", "petal_width"]
TARGET_COLUMN = "species"


def main():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Missing data file: {DATA_PATH}")
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Missing model file: {MODEL_PATH}")

    df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
    model = joblib.load(MODEL_PATH)
    predictions = model.predict(df[FEATURE_COLUMNS])

    metric_payload = {
        "rows": int(len(df)),
        "accuracy": float(metrics.accuracy_score(df[TARGET_COLUMN], predictions)),
        "precision_weighted": float(metrics.precision_score(df[TARGET_COLUMN], predictions, average="weighted", zero_division=0)),
        "recall_weighted": float(metrics.recall_score(df[TARGET_COLUMN], predictions, average="weighted", zero_division=0)),
        "f1_weighted": float(metrics.f1_score(df[TARGET_COLUMN], predictions, average="weighted", zero_division=0)),
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(json.dumps(metric_payload, indent=2), encoding="utf-8")

    report = f"""# Week 4 CI Model Evaluation

| Metric | Value |
| --- | ---: |
| Rows | {metric_payload["rows"]} |
| Accuracy | {metric_payload["accuracy"]:.4f} |
| Precision weighted | {metric_payload["precision_weighted"]:.4f} |
| Recall weighted | {metric_payload["recall_weighted"]:.4f} |
| F1 weighted | {metric_payload["f1_weighted"]:.4f} |

Data source: `week4-v1/data/iris.csv`

Model source: `week4-v1/models/model.joblib`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
