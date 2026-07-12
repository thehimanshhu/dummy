import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from feast import FeatureStore
from google.cloud import bigquery
from sklearn import metrics


REPO_ROOT = Path(__file__).resolve().parents[2]
WEEK4_DIR = REPO_ROOT / "week4-v1"
FEATURE_REPO_PATH = WEEK4_DIR / "feature_repo"

DATA_PATH = WEEK4_DIR / "data" / "iris.csv"
MODEL_PATH = WEEK4_DIR / "models" / "model.joblib"
REPORT_DIR = Path(__file__).resolve().parents[1] / "reports"
REPORT_PATH = REPORT_DIR / "dvc_feast_validation_report.md"
METRICS_PATH = REPORT_DIR / "dvc_feast_validation_metrics.json"
PREDICTIONS_PATH = REPORT_DIR / "dvc_feast_predictions.csv"
ENTITY_ROWS_PATH = WEEK4_DIR / "data" / "entity_rows.csv"

FEATURE_COLUMNS = ["sepal_length", "sepal_width", "petal_length", "petal_width"]
TARGET_COLUMN = "species"
EVENT_TIMESTAMP = pd.Timestamp("2026-01-01T00:00:00Z")

PROJECT_ID = os.getenv("PROJECT_ID", "your-gcp-project-id")
BIGQUERY_DATASET = os.getenv("BIGQUERY_DATASET", "iris_feast_week4")
BIGQUERY_TABLE = os.getenv("BIGQUERY_TABLE", "iris_features")
BIGQUERY_LOCATION = os.getenv("BIGQUERY_LOCATION", "US")
MATERIALIZE_START = os.getenv("MATERIALIZE_START", "2025-01-01T00:00:00")
MATERIALIZE_END = os.getenv("MATERIALIZE_END", "2027-01-01T00:00:00")
SAMPLE_IDS = [
    int(value.strip())
    for value in os.getenv("INFERENCE_SAMPLE_IDS", "0,10,20").split(",")
    if value.strip()
]


def now_timestamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def run_command(command, cwd=None):
    subprocess.run(command, cwd=cwd, check=True)


def require_inputs():
    if PROJECT_ID == "your-gcp-project-id":
        raise RuntimeError("Set PROJECT_ID before running the combined DVC + Feast pipeline.")
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Missing DVC data file: {DATA_PATH}. Run dvc pull in week4-v1.")
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Missing DVC model file: {MODEL_PATH}. Run dvc pull in week4-v1.")
    if not FEATURE_REPO_PATH.exists():
        raise FileNotFoundError(f"Missing Feast repo: {FEATURE_REPO_PATH}")


def load_dvc_data():
    df = pd.read_csv(DATA_PATH, encoding="utf-8-sig").reset_index(drop=True)
    missing = [column for column in [*FEATURE_COLUMNS, TARGET_COLUMN] if column not in df.columns]
    if missing:
        raise ValueError(f"Week 2 DVC data is missing required columns: {missing}")
    df.insert(0, "sample_id", df.index.astype("int64"))
    df["event_timestamp"] = EVENT_TIMESTAMP
    return df


def upload_features_to_bigquery(df):
    client = bigquery.Client(project=PROJECT_ID)
    dataset_id = f"{PROJECT_ID}.{BIGQUERY_DATASET}"
    table_id = f"{dataset_id}.{BIGQUERY_TABLE}"

    dataset = bigquery.Dataset(dataset_id)
    dataset.location = BIGQUERY_LOCATION
    client.create_dataset(dataset, exists_ok=True)

    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        schema=[
            bigquery.SchemaField("sample_id", "INTEGER"),
            bigquery.SchemaField("event_timestamp", "TIMESTAMP"),
            bigquery.SchemaField("sepal_length", "FLOAT"),
            bigquery.SchemaField("sepal_width", "FLOAT"),
            bigquery.SchemaField("petal_length", "FLOAT"),
            bigquery.SchemaField("petal_width", "FLOAT"),
            bigquery.SchemaField(TARGET_COLUMN, "STRING"),
        ],
    )
    client.load_table_from_dataframe(df, table_id, job_config=job_config).result()
    return table_id, client.get_table(table_id).num_rows


def write_entity_rows(df):
    ENTITY_ROWS_PATH.parent.mkdir(parents=True, exist_ok=True)
    df[["sample_id", "event_timestamp", TARGET_COLUMN]].to_csv(ENTITY_ROWS_PATH, index=False)


def write_feast_definitions():
    feature_store_yaml = f"""project: iris_feature_store_week4
provider: gcp
registry: data/registry.db
offline_store:
  type: bigquery
  dataset: {BIGQUERY_DATASET}
online_store:
  type: sqlite
  path: data/online_store.db
entity_key_serialization_version: 3
"""
    iris_features_py = """import os
from datetime import timedelta

from feast import BigQuerySource, Entity, FeatureView, Field, ValueType
from feast.types import Float32


PROJECT_ID = os.getenv("PROJECT_ID", "your-gcp-project-id")
BIGQUERY_DATASET = os.getenv("BIGQUERY_DATASET", "iris_feast_week4")
BIGQUERY_TABLE = os.getenv("BIGQUERY_TABLE", "iris_features")

iris_sample = Entity(
    name="iris_sample",
    join_keys=["sample_id"],
    value_type=ValueType.INT64,
    description="One Iris sample from the Week 4 DVC-versioned dataset.",
)

iris_source = BigQuerySource(
    name="iris_source",
    table=f"{PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}",
    timestamp_field="event_timestamp",
)

iris_feature_view = FeatureView(
    name="iris_features",
    entities=[iris_sample],
    ttl=timedelta(days=3650),
    schema=[
        Field(name="sepal_length", dtype=Float32),
        Field(name="sepal_width", dtype=Float32),
        Field(name="petal_length", dtype=Float32),
        Field(name="petal_width", dtype=Float32),
    ],
    source=iris_source,
)
"""
    (FEATURE_REPO_PATH / "feature_store.yaml").write_text(feature_store_yaml, encoding="utf-8")
    (FEATURE_REPO_PATH / "iris_features.py").write_text(iris_features_py, encoding="utf-8")


def apply_and_materialize():
    env = os.environ.copy()
    env["PROJECT_ID"] = PROJECT_ID
    env["GOOGLE_CLOUD_PROJECT"] = PROJECT_ID
    env["BIGQUERY_DATASET"] = BIGQUERY_DATASET
    env["BIGQUERY_TABLE"] = BIGQUERY_TABLE

    subprocess.run(["feast", "apply"], cwd=FEATURE_REPO_PATH, env=env, check=True)
    subprocess.run(
        ["feast", "materialize", MATERIALIZE_START, MATERIALIZE_END],
        cwd=FEATURE_REPO_PATH,
        env=env,
        check=True,
    )


def evaluate_with_feast_features(df):
    model = joblib.load(MODEL_PATH)
    store = FeatureStore(repo_path=str(FEATURE_REPO_PATH))
    feature_refs = [f"iris_features:{column}" for column in FEATURE_COLUMNS]

    sample_ids = [sample_id for sample_id in SAMPLE_IDS if sample_id in set(df["sample_id"])]
    if not sample_ids:
        raise ValueError("No valid sample ids were provided for online inference.")

    online_df = store.get_online_features(
        features=feature_refs,
        entity_rows=[{"sample_id": sample_id} for sample_id in sample_ids],
    ).to_df()
    raw_rows = df[df["sample_id"].isin(sample_ids)].set_index("sample_id").loc[sample_ids].reset_index()

    online_predictions = model.predict(online_df[FEATURE_COLUMNS])
    raw_predictions = model.predict(raw_rows[FEATURE_COLUMNS])
    full_predictions = model.predict(df[FEATURE_COLUMNS])

    prediction_df = pd.DataFrame({
        "sample_id": sample_ids,
        "actual_label": raw_rows[TARGET_COLUMN].to_numpy(),
        "online_prediction": online_predictions,
        "raw_data_prediction": raw_predictions,
        "predictions_match": online_predictions == raw_predictions,
    })

    metric_payload = {
        "run_id": "dvc-feast-validation-" + now_timestamp(),
        "dvc_data_path": str(DATA_PATH),
        "dvc_model_path": str(MODEL_PATH),
        "feature_repo_path": str(FEATURE_REPO_PATH),
        "bigquery_table": f"{PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}",
        "rows": int(len(df)),
        "sample_ids": sample_ids,
        "accuracy_on_dvc_data": float(metrics.accuracy_score(df[TARGET_COLUMN], full_predictions)),
        "f1_weighted_on_dvc_data": float(metrics.f1_score(df[TARGET_COLUMN], full_predictions, average="weighted", zero_division=0)),
        "online_predictions_match_raw_features": bool(prediction_df["predictions_match"].all()),
    }
    return metric_payload, prediction_df


def write_report(metric_payload, prediction_df):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(json.dumps(metric_payload, indent=2), encoding="utf-8")
    prediction_df.to_csv(PREDICTIONS_PATH, index=False)

    prediction_rows = "\n".join(
        "| {sample_id} | {actual_label} | {online_prediction} | {raw_data_prediction} | {predictions_match} |".format(**row)
        for row in prediction_df.to_dict(orient="records")
    )
    report = f"""# Week 4 Combined DVC + Feast Validation

| Check | Value |
| --- | --- |
| DVC data | `{metric_payload["dvc_data_path"]}` |
| DVC model | `{metric_payload["dvc_model_path"]}` |
| Feast repo | `{metric_payload["feature_repo_path"]}` |
| BigQuery table | `{metric_payload["bigquery_table"]}` |
| Rows evaluated | {metric_payload["rows"]} |
| Accuracy on DVC data | {metric_payload["accuracy_on_dvc_data"]:.4f} |
| Weighted F1 on DVC data | {metric_payload["f1_weighted_on_dvc_data"]:.4f} |
| Online predictions match raw features | {metric_payload["online_predictions_match_raw_features"]} |

## Online Prediction Samples

| sample_id | actual_label | online_prediction | raw_data_prediction | predictions_match |
| ---: | --- | --- | --- | --- |
{prediction_rows}
"""
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report)


def main():
    require_inputs()
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", PROJECT_ID)
    os.environ["BIGQUERY_DATASET"] = BIGQUERY_DATASET
    os.environ["BIGQUERY_TABLE"] = BIGQUERY_TABLE

    df = load_dvc_data()
    table_id, rows_loaded = upload_features_to_bigquery(df)
    write_entity_rows(df)
    write_feast_definitions()
    apply_and_materialize()
    metric_payload, prediction_df = evaluate_with_feast_features(df)
    metric_payload["bigquery_rows_loaded"] = int(rows_loaded)
    metric_payload["bigquery_table"] = table_id
    write_report(metric_payload, prediction_df)


if __name__ == "__main__":
    main()
