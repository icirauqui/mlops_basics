"""Summarize logged predictions, input drift, and delayed ground-truth labels."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from iris_mlops.data import FEATURES, SPECIES
from iris_mlops.workflow import read_json, verify_bundle, write_json


def read_events(path):
    return [
        json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()
    ]


def summarize(bundle, events, feedback=None, min_samples=30):
    metadata = verify_bundle(bundle)
    baseline = read_json(Path(bundle) / "baseline.json")
    events = [
        event
        for event in events
        if event.get("event") == "prediction"
        and event["model_version"] == metadata["run_id"]
    ]
    rows = []
    predictions = {}
    for event in events:
        if len(event["instances"]) != len(event["predictions"]):
            raise ValueError("Log has different numbers of instances and predictions")
        for index, (row, prediction) in enumerate(
            zip(event["instances"], event["predictions"])
        ):
            key = (event["request_id"], index)
            if key in predictions:
                raise ValueError(
                    "Duplicate request IDs in logs; deduplicate exported records"
                )
            predictions[key] = prediction
            rows.append(row)
    report = {
        "model_version": metadata["run_id"],
        "requests": len(events),
        "samples": len(rows),
        "enough_data": len(rows) >= min_samples,
        "drift": None,
        "labeled_samples": 0,
        "accuracy": None,
        "alerts": [],
    }
    report["latency_p95_ms"] = (
        float(np.percentile([e["latency_ms"] for e in events], 95)) if events else None
    )
    if report["enough_data"]:
        # Educational signal, not a statistical test: movement in training std units.
        mean = pd.DataFrame(rows, columns=FEATURES).mean()
        shifts = {
            feature: float(
                abs(mean[feature] - baseline["mean"][feature])
                / max(baseline["std"][feature], 1e-6)
            )
            for feature in FEATURES
        }
        report["drift"] = shifts
        if max(shifts.values()) > 1.0:
            report["alerts"].append(
                "Input mean shifted by more than one training standard deviation"
            )
    matches = []
    seen = set()
    for label in feedback or []:
        key = (label["request_id"], label["row_index"])
        if key in seen or label["label"] not in SPECIES:
            raise ValueError(
                "Feedback must have unique request/row keys and valid species labels"
            )
        seen.add(key)
        if key in predictions:
            matches.append(predictions[key] == label["label"])
    report["labeled_samples"] = len(matches)
    if matches:
        report["accuracy"] = sum(matches) / len(matches)
        if len(matches) >= min_samples and report["accuracy"] < 0.9:
            report["alerts"].append(
                "Labeled accuracy below 90%; investigate before retraining"
            )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument("--feedback", type=Path)
    parser.add_argument("--output", type=Path, default=Path("state/monitoring.json"))
    args = parser.parse_args()
    report = summarize(
        args.bundle,
        read_events(args.log),
        read_events(args.feedback) if args.feedback else None,
    )
    write_json(args.output, report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
