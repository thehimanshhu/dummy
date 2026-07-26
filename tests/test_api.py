from unittest.mock import Mock

import numpy as np
import pytest
from pydantic import ValidationError

import app.main as api


def fake_model():
    model = Mock()
    model.classes_ = np.array(["setosa", "versicolor", "virginica"])
    model.predict.return_value = np.array(["setosa"])
    model.predict_proba.return_value = np.array([[0.98, 0.01, 0.01]])
    return model


def test_health_reports_loaded_model(monkeypatch):
    monkeypatch.setattr(api, "load_model", fake_model)

    response = api.health()

    assert response == {"status": "healthy", "model": "model.joblib"}


def test_predict_returns_class_and_probabilities(monkeypatch):
    model = fake_model()
    monkeypatch.setattr(api, "load_model", lambda: model)

    response = api.predict(
        api.IrisFeatures(
            sepal_length=5.1,
            sepal_width=3.5,
            petal_length=1.4,
            petal_width=0.2,
        )
    )

    assert response.model_dump() == {
        "prediction": "setosa",
        "probabilities": {
            "setosa": 0.98,
            "versicolor": 0.01,
            "virginica": 0.01,
        },
    }
    assert list(model.predict.call_args.args[0].columns) == [
        "sepal_length",
        "sepal_width",
        "petal_length",
        "petal_width",
    ]


def test_predict_rejects_non_positive_measurements():
    with pytest.raises(ValidationError):
        api.IrisFeatures(
            sepal_length=0,
            sepal_width=3.5,
            petal_length=1.4,
            petal_width=0.2,
        )


def test_required_routes_are_registered():
    paths = {route.path for route in api.app.routes}

    assert {"/health", "/predict", "/docs"} <= paths
