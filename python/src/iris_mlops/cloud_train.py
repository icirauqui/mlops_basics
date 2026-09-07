"""Managed training job entry point shared by Azure ML and SageMaker AI."""

import argparse
import shutil
import tempfile
from pathlib import Path

from iris_mlops.workflow import evaluate, run_path, train_run


def train(data_dir, output, C=1.0):
    with tempfile.TemporaryDirectory() as root:
        run_id = train_run(data_dir, root=root, C=C)
        gate = evaluate(run_id, root=root)
        # A managed training job produces a candidate, never a production approval.
        shutil.copytree(run_path(run_id, root), output, dirs_exist_ok=True)
        print(f"run_id={run_id}; validation_accuracy={gate['validation']['accuracy']}")
        return run_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--C", type=float, default=1.0)
    args = parser.parse_args()
    train(args.data, args.output, args.C)


if __name__ == "__main__":
    main()
