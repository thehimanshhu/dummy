from pathlib import Path


WEEK4_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = WEEK4_DIR / "data" / "iris.csv"
MODEL_PATH = WEEK4_DIR / "models" / "model.joblib"
METRICS_PATH = WEEK4_DIR / "metrics" / "metrics.json"

FEATURE_COLUMNS = ["sepal_length", "sepal_width", "petal_length", "petal_width"]
TARGET_COLUMN = "species"
EXPECTED_LABELS = {"setosa", "versicolor", "virginica"}
