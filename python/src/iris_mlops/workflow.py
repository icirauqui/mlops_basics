"""Small file-based experiment tracker and model registry for one operator."""

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import tarfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import joblib
import sklearn
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix

from iris_mlops.data import DATA_DIR, FEATURES, SPECIES, SPLITS, sha256, validate_data
from iris_mlops.train import train_model

from iris_mlops.paths import PROJECT_DIR as BASE_DIR

PACKAGE_DIR = Path(__file__).resolve().parent
STATE_DIR = BASE_DIR / "state"
POLICY = {"min_accuracy": 0.9, "min_macro_f1": 0.9, "max_regression": 0.02}
BUNDLE_FILES = [
    "model.joblib",
    "run.json",
    "baseline.json",
    "gate.json",
    "release.json",
]


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    """Atomic replacement for this single-operator course registry."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def run_path(run_id, root=STATE_DIR):
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", run_id):
        raise ValueError("Run ID must be 1–80 letters, digits, underscores, or hyphens")
    return Path(root) / "runs" / run_id


def registry(root=STATE_DIR):
    path = Path(root) / "registry.json"
    return read_json(path) if path.exists() else {"production": None, "history": []}


def score(model, frame):
    predictions = model.predict(frame[FEATURES])
    return {
        "accuracy": float(accuracy_score(frame.label, predictions)),
        "macro_f1": float(
            f1_score(frame.label, predictions, labels=SPECIES, average="macro")
        ),
        "confusion_matrix": confusion_matrix(
            frame.label, predictions, labels=SPECIES
        ).tolist(),
        "rows": len(frame),
    }


def verify_run(directory):
    directory = Path(directory)
    metadata = read_json(directory / "run.json")
    if metadata["model_sha256"] != sha256(directory / "model.joblib"):
        raise ValueError("Model checksum mismatch")
    if metadata["baseline_sha256"] != sha256(directory / "baseline.json"):
        raise ValueError("Baseline checksum mismatch")
    return metadata


def train_run(data_dir=DATA_DIR, root=STATE_DIR, C=1.0, run_id=None):
    frames = validate_data(data_dir)
    run_id = (
        run_id
        or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        + "-"
        + uuid.uuid4().hex[:8]
    )
    directory = run_path(run_id, root)
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "data").mkdir()
    for split in SPLITS:
        shutil.copyfile(
            Path(data_dir) / f"{split}.csv", directory / "data" / f"{split}.csv"
        )
    model = train_model(frames["train"][FEATURES], frames["train"].label, C=C)
    joblib.dump(model, directory / "model.joblib")
    baseline = {
        "mean": frames["train"][FEATURES].mean().to_dict(),
        "std": frames["train"][FEATURES].std(ddof=0).to_dict(),
        "rows": len(frames["train"]),
    }
    write_json(directory / "baseline.json", baseline)
    source_files = sorted(PACKAGE_DIR.glob("*.py")) + [BASE_DIR / "uv.lock"]
    sources = {file.name: sha256(file) for file in source_files if file.exists()}
    git = (
        subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            check=False,
        )
        if shutil.which("git")
        else None
    )
    metadata = {
        "run_id": run_id,
        "created_at": now(),
        "parameters": {"C": C, "max_iter": 200},
        "python": platform.python_version(),
        "sklearn": sklearn.__version__,
        "git_commit": git.stdout.strip() if git and git.returncode == 0 else None,
        "source_sha256": hashlib.sha256(
            json.dumps(sources, sort_keys=True).encode()
        ).hexdigest(),
        "source_files": sources,
        "data_sha256": {
            split: sha256(directory / "data" / f"{split}.csv") for split in SPLITS
        },
        "model_sha256": sha256(directory / "model.joblib"),
        "baseline_sha256": sha256(directory / "baseline.json"),
    }
    write_json(directory / "run.json", metadata)
    write_json(
        directory / "metrics.json", {"validation": score(model, frames["validation"])}
    )
    return run_id


def evaluate(run_id, root=STATE_DIR):
    """Evaluate validation data against absolute and incumbent-relative gates."""
    directory = run_path(run_id, root)
    metadata = verify_run(directory)
    frames = validate_data(directory / "data")
    for split in SPLITS:
        if (
            sha256(directory / "data" / f"{split}.csv")
            != metadata["data_sha256"][split]
        ):
            raise ValueError(f"Modified {split} data in immutable run")
    model = joblib.load(directory / "model.joblib")
    metrics = score(model, frames["validation"])
    reasons = []
    if metrics["accuracy"] < POLICY["min_accuracy"]:
        reasons.append("Validation accuracy below minimum")
    if metrics["macro_f1"] < POLICY["min_macro_f1"]:
        reasons.append("Validation macro F1 below minimum")
    champion = registry(root)["production"]
    champion_metrics = None
    if champion and champion != run_id:
        champion_dir = run_path(champion, root)
        champion_metadata = verify_run(champion_dir)
        for split in ["validation", "test"]:
            if (
                metadata["data_sha256"][split]
                != champion_metadata["data_sha256"][split]
            ):
                reasons.append(
                    f"Changed {split} benchmark; start a separately reviewed registry"
                )
        champion_metrics = score(
            joblib.load(champion_dir / "model.joblib"), frames["validation"]
        )
        for metric in ["accuracy", "macro_f1"]:
            if metrics[metric] + POLICY["max_regression"] < champion_metrics[metric]:
                reasons.append(f"Validation {metric} regressed against production")
    gate = {
        "run_id": run_id,
        "evaluated_at": now(),
        "passed": not reasons,
        "reasons": reasons,
        "policy": POLICY,
        "validation": metrics,
        "compared_to": champion,
        "champion_validation": champion_metrics,
        "model_sha256": metadata["model_sha256"],
    }
    write_json(directory / "gate.json", gate)
    return gate


def promote(run_id, root=STATE_DIR):
    """Recheck the gate, record a decision, and move the local production pointer."""
    gate = evaluate(run_id, root)
    if not gate["passed"]:
        raise ValueError("Promotion rejected: " + "; ".join(gate["reasons"]))
    state = registry(root)
    if state["production"] != run_id:
        state["history"].append(
            {
                "at": now(),
                "action": "promote",
                "from": state["production"],
                "to": run_id,
            }
        )
        state["production"] = run_id
        write_json(Path(root) / "registry.json", state)
    return state


def rollback(run_id, root=STATE_DIR):
    """Restore an explicitly named, previously promoted version."""
    state = registry(root)
    if not any(
        event["action"] == "promote" and event["to"] == run_id
        for event in state["history"]
    ):
        raise ValueError("Rollback target must have been promoted previously")
    verify_run(run_path(run_id, root))
    state["history"].append(
        {"at": now(), "action": "rollback", "from": state["production"], "to": run_id}
    )
    state["production"] = run_id
    write_json(Path(root) / "registry.json", state)
    return state


def final_test(run_id, root=STATE_DIR):
    """Report the untouched test split once after selecting a production model."""
    if registry(root)["production"] != run_id:
        raise ValueError("Select and promote the model before opening the test set")
    directory = run_path(run_id, root)
    metadata = verify_run(directory)
    path = directory / "final-test.json"
    if not path.exists():
        frames = validate_data(directory / "data")
        if sha256(directory / "data" / "test.csv") != metadata["data_sha256"]["test"]:
            raise ValueError("Test checksum mismatch")
        write_json(path, score(joblib.load(directory / "model.joblib"), frames["test"]))
    return read_json(path)


def export_bundle(run_id, output, root=STATE_DIR):
    if registry(root)["production"] != run_id:
        raise ValueError("Export requires the current production version")
    directory = run_path(run_id, root)
    metadata = verify_run(directory)
    gate = read_json(directory / "gate.json")
    if not gate["passed"] or gate["model_sha256"] != metadata["model_sha256"]:
        raise ValueError("Missing passing evaluation for this model")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    for name in BUNDLE_FILES[:-1]:
        shutil.copyfile(directory / name, output / name)
    write_json(
        output / "release.json",
        {
            "run_id": run_id,
            "approved": True,
            "exported_at": now(),
            "sha256": {name: sha256(output / name) for name in BUNDLE_FILES[:-1]},
        },
    )
    # SageMaker expects files at the archive root, not inside an extra folder.
    with tarfile.open(str(output) + ".tar.gz", "w:gz") as archive:
        for name in BUNDLE_FILES:
            archive.add(output / name, arcname=name)
    return output


def verify_bundle(directory):
    directory = Path(directory)
    release = read_json(directory / "release.json")
    if release["approved"] is not True or set(release["sha256"]) != set(
        BUNDLE_FILES[:-1]
    ):
        raise ValueError("Not an approved course release")
    for name, expected in release["sha256"].items():
        if sha256(directory / name) != expected:
            raise ValueError(f"Release checksum mismatch: {name}")
    metadata = verify_run(directory)
    gate = read_json(directory / "gate.json")
    if (
        release["run_id"] != metadata["run_id"]
        or not gate["passed"]
        or gate["model_sha256"] != metadata["model_sha256"]
    ):
        raise ValueError("Release approval does not match the model")
    return metadata


def import_run(source, root=STATE_DIR):
    """Import a downloaded cloud training run; it still needs local promotion."""
    source = Path(source)
    metadata = verify_run(source)
    validate_data(source / "data")
    for split in SPLITS:
        if sha256(source / "data" / f"{split}.csv") != metadata["data_sha256"][split]:
            raise ValueError("Downloaded data checksum mismatch")
    destination = run_path(metadata["run_id"], root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    return metadata["run_id"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=STATE_DIR)
    commands = parser.add_subparsers(dest="action", required=True)
    train = commands.add_parser("train")
    train.add_argument("--data", type=Path, default=DATA_DIR)
    train.add_argument("--C", type=float, default=1.0)
    train.add_argument("--run-id")
    for action in ["evaluate", "promote", "rollback", "test", "export"]:
        command = commands.add_parser(action)
        command.add_argument("run_id")
        if action == "export":
            command.add_argument("--output", required=True, type=Path)
    commands.add_parser("status")
    commands.add_parser("import").add_argument("source", type=Path)
    args = parser.parse_args()
    if args.action == "train":
        result = train_run(args.data, args.root, args.C, args.run_id)
    elif args.action == "status":
        result = registry(args.root)
    elif args.action == "import":
        result = import_run(args.source, args.root)
    elif args.action == "export":
        result = str(export_bundle(args.run_id, args.output, args.root))
    else:
        function = {
            "evaluate": evaluate,
            "promote": promote,
            "rollback": rollback,
            "test": final_test,
        }[args.action]
        result = function(args.run_id, args.root)
    print(result if isinstance(result, str) else json.dumps(result, indent=2))
    if args.action == "evaluate" and not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
