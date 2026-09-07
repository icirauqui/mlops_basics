"""Append reviewed, labeled training examples; evaluate a new candidate."""

import argparse
import json
import shutil
from pathlib import Path

import pandas as pd

from iris_mlops.data import DATA_DIR, FEATURES, validate_data
from iris_mlops.workflow import STATE_DIR, evaluate, train_run


def retrain(new_labels, output_data, data_dir=DATA_DIR, root=STATE_DIR, C=1.0):
    frames = validate_data(data_dir)
    additions = pd.read_csv(new_labels)
    if list(additions.columns) != ["sample_id", *FEATURES, "label"] or additions.empty:
        raise ValueError("New labels must use the existing non-empty CSV schema")
    output_data = Path(output_data)
    output_data.mkdir(parents=True, exist_ok=False)
    pd.concat([frames["train"], additions], ignore_index=True).to_csv(
        output_data / "train.csv", index=False
    )
    for split in ["validation", "test"]:
        shutil.copyfile(Path(data_dir) / f"{split}.csv", output_data / f"{split}.csv")
    validate_data(output_data)
    run_id = train_run(output_data, root=root, C=C)
    return {"run_id": run_id, "gate": evaluate(run_id, root=root)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new-labels", required=True, type=Path)
    parser.add_argument("--output-data", required=True, type=Path)
    parser.add_argument("--data", type=Path, default=DATA_DIR)
    parser.add_argument("--root", type=Path, default=STATE_DIR)
    parser.add_argument("--C", type=float, default=1.0)
    args = parser.parse_args()
    print(
        json.dumps(
            retrain(args.new_labels, args.output_data, args.data, args.root, args.C),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
