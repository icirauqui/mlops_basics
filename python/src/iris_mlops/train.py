"""Train and evaluate a small Iris classifier. Run with: uv run python -m iris_mlops.train."""

import json
from pathlib import Path

from iris_mlops.paths import PROJECT_DIR

import joblib
from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ARTIFACTS_DIR = PROJECT_DIR / "artifacts"


def split_data(iris, test_size=0.2, random_state=42):
    """Keep the same class proportions in the training and test sets."""
    return train_test_split(
        iris.data,
        iris.target,
        test_size=test_size,
        random_state=random_state,
        stratify=iris.target,
    )


def train_model(X_train, y_train, C=1.0):
    """Learn scaling and classification using only the training rows."""
    model = make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=200))
    model.fit(X_train, y_train)
    return model


def evaluate_model(model, X_test, y_test, target_names):
    """Return accuracy and per-species precision, recall, and F1 scores."""
    return classification_report(
        y_test,
        model.predict(X_test),
        labels=model.classes_,
        target_names=target_names,
        output_dict=True,
        zero_division=0,
    )


def save_artifacts(model, metrics, output_dir=ARTIFACTS_DIR):
    """Save the complete fitted pipeline and its test metrics."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output_dir / "model.joblib")
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
    )


def main():
    iris = load_iris(as_frame=True)
    X_train, X_test, y_train, y_test = split_data(iris)
    model = train_model(X_train, y_train)
    metrics = evaluate_model(model, X_test, y_test, iris.target_names)
    save_artifacts(model, metrics)
    print(f"Training rows: {len(X_train)} | Test rows: {len(X_test)}")
    print(f"Test accuracy: {metrics['accuracy']:.1%}")
    print(f"Saved model and metrics to {ARTIFACTS_DIR}")


if __name__ == "__main__":
    main()
