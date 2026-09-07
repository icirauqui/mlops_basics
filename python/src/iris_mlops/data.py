"""Create and validate versionable train/validation/test CSV snapshots."""

import argparse
import hashlib
from pathlib import Path

from iris_mlops.paths import PROJECT_DIR

import numpy as np
import pandas as pd
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split

FEATURES = ["sepal_length", "sepal_width", "petal_length", "petal_width"]
SPECIES = ["setosa", "versicolor", "virginica"]
SPLITS = ["train", "validation", "test"]
DATA_DIR = PROJECT_DIR / "data" / "iris"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare_data(output=DATA_DIR):
    """Write a fixed 60/20/20 split; never overwrite an existing snapshot."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    iris = load_iris()
    frame = pd.DataFrame(iris.data, columns=FEATURES)
    frame.insert(0, "sample_id", [f"iris-{i:03d}" for i in range(len(frame))])
    frame["label"] = [SPECIES[i] for i in iris.target]
    development, test = train_test_split(
        frame, test_size=0.2, stratify=frame.label, random_state=42
    )
    train, validation = train_test_split(
        development, test_size=0.25, stratify=development.label, random_state=42
    )
    for name, split in zip(SPLITS, [train, validation, test]):
        split.to_csv(output / f"{name}.csv", index=False)
    return validate_data(output)


def validate_data(directory):
    """Check schema, labels, numerical values, and split isolation."""
    frames = {}
    seen_ids = set()
    for split in SPLITS:
        frame = pd.read_csv(Path(directory) / f"{split}.csv")
        if list(frame.columns) != ["sample_id", *FEATURES, "label"]:
            raise ValueError(f"{split}: expected sample_id, {FEATURES}, label in order")
        if frame.empty or frame.isna().any().any():
            raise ValueError(f"{split}: empty data or missing values")
        values = frame[FEATURES].to_numpy(dtype=float)
        if not np.isfinite(values).all() or (values <= 0).any() or (values > 30).any():
            raise ValueError(f"{split}: measurements must be finite and in (0, 30] cm")
        if set(frame.label) != set(SPECIES) or frame.label.value_counts().min() < 2:
            raise ValueError(f"{split}: need at least two examples of each species")
        ids = set(frame.sample_id)
        if len(ids) != len(frame) or ids & seen_ids:
            raise ValueError(f"{split}: duplicate sample IDs within or across splits")
        seen_ids.update(ids)
        frames[split] = frame
    return frames


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "validate"])
    parser.add_argument("--directory", type=Path, default=DATA_DIR)
    args = parser.parse_args()
    frames = (
        prepare_data(args.directory)
        if args.action == "prepare"
        else validate_data(args.directory)
    )
    print({name: len(frame) for name, frame in frames.items()})


if __name__ == "__main__":
    main()
