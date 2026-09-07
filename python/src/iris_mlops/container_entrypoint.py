"""Support SageMaker's train/serve commands and normal Docker commands."""

import json
import os
import sys
from pathlib import Path


def main():
    args = sys.argv[1:] or ["serve"]
    if args[0] == "train":
        from iris_mlops.cloud_train import train

        config = Path("/opt/ml/input/config/hyperparameters.json")
        parameters = json.loads(config.read_text()) if config.exists() else {}
        try:
            train(
                Path("/opt/ml/input/data/training"),
                Path("/opt/ml/model"),
                float(parameters.get("C", 1.0)),
            )
        except Exception as error:
            failure = Path("/opt/ml/output/failure")
            try:
                failure.parent.mkdir(parents=True, exist_ok=True)
                failure.write_text(str(error))
            except OSError:
                print(f"Training failed: {error}", file=sys.stderr)
            raise
    elif args[0] == "serve":
        os.execvp(
            "uvicorn",
            ["uvicorn", "iris_mlops.serve:app", "--host", "0.0.0.0", "--port", "8080"],
        )
    else:
        os.execvp(args[0], args)


if __name__ == "__main__":
    main()
