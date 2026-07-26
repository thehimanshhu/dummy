import os
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


APP_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = Path(os.getenv("MODEL_PATH", APP_ROOT / "models" / "model.joblib"))
FEATURE_COLUMNS = [
    "sepal_length",
    "sepal_width",
    "petal_length",
    "petal_width",
]

app = FastAPI(
    title="Iris Inference API",
    description="Serves predictions from the validated Iris classification model.",
    version="1.0.0",
)


class IrisFeatures(BaseModel):
    sepal_length: float = Field(gt=0)
    sepal_width: float = Field(gt=0)
    petal_length: float = Field(gt=0)
    petal_width: float = Field(gt=0)


class PredictionResponse(BaseModel):
    prediction: str
    probabilities: dict[str, float] | None = None


@lru_cache(maxsize=1)
def load_model():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model not found at {MODEL_PATH}. Run 'dvc pull models/model.joblib.dvc' first."
        )
    return joblib.load(MODEL_PATH)


@app.get("/health")
def health():
    try:
        load_model()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"status": "healthy", "model": MODEL_PATH.name}


@app.post("/predict", response_model=PredictionResponse)
def predict(features: IrisFeatures):
    try:
        model = load_model()
        input_frame = pd.DataFrame(
            [[getattr(features, column) for column in FEATURE_COLUMNS]],
            columns=FEATURE_COLUMNS,
        )
        prediction = str(model.predict(input_frame)[0])

        probabilities = None
        if hasattr(model, "predict_proba") and hasattr(model, "classes_"):
            scores = model.predict_proba(input_frame)[0]
            probabilities = {
                str(label): round(float(score), 6)
                for label, score in zip(model.classes_, scores)
            }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {exc}") from exc

    return PredictionResponse(prediction=prediction, probabilities=probabilities)
