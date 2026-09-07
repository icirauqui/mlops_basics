"""One HTTP contract for local Docker, Azure ML, and SageMaker AI."""

import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import joblib
import pandas as pd
from fastapi import FastAPI, Request
from pydantic import BaseModel, ConfigDict, Field

from iris_mlops.data import FEATURES
from iris_mlops.workflow import (
    STATE_DIR,
    now,
    registry,
    run_path,
    verify_bundle,
    verify_run,
)

Measurement = Annotated[float, Field(gt=0, le=30, allow_inf_nan=False)]


class Flower(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sepal_length: Measurement
    sepal_width: Measurement
    petal_length: Measurement
    petal_width: Measurement


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instances: list[Flower] = Field(min_length=1, max_length=100)


def create_app(model_dir=None, root=STATE_DIR, log_path=None):
    @asynccontextmanager
    async def lifespan(app):
        configured = (
            model_dir or os.getenv("MODEL_DIR") or os.getenv("AZUREML_MODEL_DIR")
        )
        if configured:
            # Azure may mount a registered model under a name/version subdirectory.
            candidates = list(Path(configured).rglob("release.json"))
            if len(candidates) != 1:
                raise ValueError("MODEL_DIR must contain exactly one approved release")
            directory = candidates[0].parent
            metadata = verify_bundle(directory)
        elif Path("/opt/ml/model/release.json").exists():
            directory = Path("/opt/ml/model")
            metadata = verify_bundle(directory)
        else:
            version = registry(root)["production"]
            if not version:
                raise ValueError(
                    "Promote a model first, or set MODEL_DIR to an exported release"
                )
            directory = run_path(version, root)
            metadata = verify_run(directory)
        app.state.model = joblib.load(directory / "model.joblib")
        app.state.version = metadata["run_id"]
        yield

    app = FastAPI(title="Iris MLOps", lifespan=lifespan)

    @app.middleware("http")
    async def request_metrics(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        print(
            json.dumps(
                {
                    "event": "http",
                    "timestamp": now(),
                    "path": request.url.path,
                    "status": response.status_code,
                    "latency_ms": round((time.perf_counter() - start) * 1000, 3),
                }
            ),
            flush=True,
        )
        return response

    @app.get("/ping")
    @app.get("/health")
    def health():
        return {"status": "ok", "model_version": app.state.version}

    @app.post("/invocations")
    @app.post("/predict")
    def predict(payload: PredictionRequest):
        start = time.perf_counter()
        rows = [flower.model_dump() for flower in payload.instances]
        frame = pd.DataFrame(rows, columns=FEATURES)
        predictions = app.state.model.predict(frame).tolist()
        probabilities = app.state.model.predict_proba(frame).tolist()
        request_id = uuid.uuid4().hex
        event = {
            "event": "prediction",
            "timestamp": now(),
            "request_id": request_id,
            "model_version": app.state.version,
            "instances": rows,
            "predictions": predictions,
            "latency_ms": round((time.perf_counter() - start) * 1000, 3),
        }
        print(json.dumps(event), flush=True)
        destination = log_path or os.getenv("PREDICTION_LOG")
        if destination:
            path = Path(destination)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event) + "\n")
        return {
            "request_id": request_id,
            "model_version": app.state.version,
            "predictions": predictions,
            "classes": app.state.model.classes_.tolist(),
            "probabilities": probabilities,
        }

    return app


app = create_app()
