import joblib
import pandas as pd
from sklearn import metrics

from conftest import DATA_PATH, EXPECTED_LABELS, FEATURE_COLUMNS, MODEL_PATH, TARGET_COLUMN


MIN_ACCURACY = 0.85
MIN_F1_WEIGHTED = 0.85


def load_data_and_model():
    assert DATA_PATH.exists(), f"Missing DVC data file: {DATA_PATH}. Run dvc pull from the repository root."
    assert MODEL_PATH.exists(), f"Missing DVC model file: {MODEL_PATH}. Run dvc pull from the repository root."
    df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
    model = joblib.load(MODEL_PATH)
    return df, model


def test_model_file_loads_successfully():
    _, model = load_data_and_model()
    assert hasattr(model, "predict")


def test_model_predictions_have_expected_shape_and_labels():
    df, model = load_data_and_model()
    predictions = model.predict(df[FEATURE_COLUMNS])
    assert len(predictions) == len(df)
    assert set(predictions) <= EXPECTED_LABELS


def test_model_quality_meets_minimum_thresholds():
    df, model = load_data_and_model()
    predictions = model.predict(df[FEATURE_COLUMNS])
    accuracy = metrics.accuracy_score(df[TARGET_COLUMN], predictions)
    f1_weighted = metrics.f1_score(df[TARGET_COLUMN], predictions, average="weighted", zero_division=0)

    assert accuracy >= MIN_ACCURACY
    assert f1_weighted >= MIN_F1_WEIGHTED
