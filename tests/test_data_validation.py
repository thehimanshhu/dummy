import pandas as pd

from conftest import DATA_PATH, EXPECTED_LABELS, FEATURE_COLUMNS, TARGET_COLUMN


def load_dataset():
    assert DATA_PATH.exists(), f"Missing DVC data file: {DATA_PATH}. Run dvc pull in week4-v1."
    return pd.read_csv(DATA_PATH, encoding="utf-8-sig")


def test_dataset_has_expected_schema():
    df = load_dataset()
    assert list(df.columns) == [*FEATURE_COLUMNS, TARGET_COLUMN]


def test_dataset_has_no_missing_values():
    df = load_dataset()
    assert int(df.isna().sum().sum()) == 0


def test_feature_columns_are_numeric():
    df = load_dataset()
    for column in FEATURE_COLUMNS:
        assert pd.api.types.is_numeric_dtype(df[column]), f"{column} must be numeric"


def test_feature_values_are_in_reasonable_iris_ranges():
    df = load_dataset()
    ranges = {
        "sepal_length": (4.0, 8.5),
        "sepal_width": (2.0, 4.5),
        "petal_length": (1.0, 7.5),
        "petal_width": (0.1, 3.0),
    }
    for column, (lower, upper) in ranges.items():
        assert df[column].between(lower, upper).all(), f"{column} has values outside [{lower}, {upper}]"


def test_target_labels_are_expected():
    df = load_dataset()
    assert set(df[TARGET_COLUMN].unique()) <= EXPECTED_LABELS
    assert df[TARGET_COLUMN].nunique() >= 2


def test_dataset_has_enough_rows_for_evaluation():
    df = load_dataset()
    assert len(df) >= 30
