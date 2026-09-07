import copy
import json
import shutil

import joblib
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from iris_mlops.cloud_common import SAMPLE
from iris_mlops.data import FEATURES, prepare_data, sha256, validate_data
from iris_mlops.monitor import summarize
from iris_mlops.retrain import retrain
from iris_mlops.serve import create_app
from iris_mlops.workflow import (
    evaluate,
    export_bundle,
    final_test,
    import_run,
    promote,
    registry,
    rollback,
    run_path,
    train_run,
    verify_bundle,
)


@pytest.fixture
def lesson(tmp_path):
    data = tmp_path / "data"
    root = tmp_path / "state"
    prepare_data(data)
    version = train_run(data, root, run_id="baseline")
    return data, root, version


def test_train_scale_evaluate_promote_and_reload(lesson, tmp_path):
    data, root, version = lesson
    frames = validate_data(data)
    model = joblib.load(run_path(version, root) / "model.joblib")
    np.testing.assert_allclose(
        model.named_steps["standardscaler"].mean_, frames["train"][FEATURES].mean()
    )
    with pytest.raises(ValueError, match="promote"):
        final_test(version, root)
    assert evaluate(version, root)["passed"]
    promote(version, root)
    assert registry(root)["production"] == version
    bundle = export_bundle(version, tmp_path / "release", root)
    assert verify_bundle(bundle)["run_id"] == version
    loaded = joblib.load(bundle / "model.joblib")
    np.testing.assert_array_equal(
        model.predict(frames["test"][FEATURES]),
        loaded.predict(frames["test"][FEATURES]),
    )
    assert final_test(version, root)["rows"] == 30


def test_reject_weak_model_and_unapproved_rollback(lesson):
    data, root, version = lesson
    promote(version, root)
    weak = train_run(data, root, C=0.000001, run_id="weak")
    assert not evaluate(weak, root)["passed"]
    with pytest.raises(ValueError, match="rejected"):
        promote(weak, root)
    with pytest.raises(ValueError, match="previously"):
        rollback(weak, root)
    assert registry(root)["production"] == version


def test_benchmark_changes_block_comparison_and_rollback_restores(lesson, tmp_path):
    data, root, version = lesson
    promote(version, root)
    other = train_run(data, root, C=10, run_id="candidate")
    promote(other, root)
    rollback(version, root)
    assert registry(root)["production"] == version
    changed = tmp_path / "changed"
    shutil.copytree(data, changed)
    frame = pd.read_csv(changed / "validation.csv")
    frame.loc[0, "sepal_length"] += 0.01
    frame.to_csv(changed / "validation.csv", index=False)
    candidate = train_run(changed, root, run_id="changed")
    assert any("benchmark" in reason for reason in evaluate(candidate, root)["reasons"])


def test_corrupt_artifact_and_duplicate_ids_fail(lesson, tmp_path):
    data, root, version = lesson
    promote(version, root)
    bundle = export_bundle(version, tmp_path / "release", root)
    with (bundle / "model.joblib").open("ab") as handle:
        handle.write(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        verify_bundle(bundle)
    frame = pd.read_csv(data / "test.csv")
    frame.loc[0, "sample_id"] = pd.read_csv(data / "train.csv").sample_id.iloc[0]
    frame.to_csv(data / "test.csv", index=False)
    with pytest.raises(ValueError, match="duplicate"):
        validate_data(data)


def test_api_contract_monitoring_and_delayed_labels(lesson, tmp_path):
    _, root, version = lesson
    promote(version, root)
    bundle = export_bundle(version, tmp_path / "release", root)
    log = tmp_path / "events.jsonl"
    with TestClient(create_app(bundle, log_path=log)) as client:
        assert client.get("/ping").json()["model_version"] == version
        response = client.post("/invocations", json=SAMPLE)
        assert response.status_code == 200
        assert response.json()["predictions"] == ["setosa"]
        malformed = copy.deepcopy(SAMPLE)
        malformed["instances"][0]["petal_width"] = -1
        assert client.post("/predict", json=malformed).status_code == 422
        assert client.post("/predict", json={"instances": []}).status_code == 422
        extra = copy.deepcopy(SAMPLE)
        extra["instances"][0]["unknown"] = 1
        assert client.post("/predict", json=extra).status_code == 422
    events = [json.loads(line) for line in log.read_text().splitlines()]
    labels = [
        {"request_id": response.json()["request_id"], "row_index": 0, "label": "setosa"}
    ]
    report = summarize(bundle, events, labels)
    assert report["accuracy"] == 1.0
    assert report["drift"] is None  # One sample must not trigger a drift claim.
    assert summarize(bundle, events)["accuracy"] is None  # Predictions aren't labels.
    shifted = []
    for i in range(30):
        event = copy.deepcopy(events[0])
        event["request_id"] = str(i)
        event["instances"][0]["petal_length"] = 15
        shifted.append(event)
    assert summarize(bundle, shifted)["alerts"]


def test_retraining_preserves_holdouts_and_cloud_import_is_unapproved(lesson, tmp_path):
    data, root, version = lesson
    promote(version, root)
    result = retrain("examples/new-labels.csv", tmp_path / "new-data", data, root)
    for split in ["validation", "test"]:
        assert sha256(data / f"{split}.csv") == sha256(
            tmp_path / "new-data" / f"{split}.csv"
        )
    assert registry(root)["production"] == version
    imported_root = tmp_path / "imported"
    imported = import_run(run_path(result["run_id"], root), imported_root)
    assert imported == result["run_id"]
    assert registry(imported_root)["production"] is None
