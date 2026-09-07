"""Predict a species from four measurements in centimeters."""

import argparse

import joblib
import pandas as pd
from sklearn.datasets import load_iris

from iris_mlops.train import ARTIFACTS_DIR


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "measurements",
        nargs=4,
        type=float,
        help="sepal length, sepal width, petal length, petal width (cm)",
    )
    args = parser.parse_args()
    model_path = ARTIFACTS_DIR / "model.joblib"
    if not model_path.exists():
        parser.error(
            "No trained model found. Run 'uv run python -m iris_mlops.train' first."
        )

    model = joblib.load(model_path)
    sample = pd.DataFrame([args.measurements], columns=model.feature_names_in_)
    species = load_iris().target_names[model.predict(sample)[0]]
    print(f"Predicted species: {species}")


if __name__ == "__main__":
    main()
