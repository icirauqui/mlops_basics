"""Small shared helpers for cloud lessons (no credentials stored here)."""

import json
import re
import tarfile
from pathlib import Path

from iris_mlops.data import FEATURES

SAMPLE = {"instances": [dict(zip(FEATURES, [5.1, 3.5, 1.4, 0.2]))]}


def immutable_image(image):
    if not re.fullmatch(r"[^\s]+@sha256:[a-f0-9]{64}", image):
        raise ValueError("Use an image URI with @sha256:<digest>, not a mutable tag")
    return image


def check_prediction(result, expected_version=None):
    if isinstance(result, (str, bytes)):
        result = json.loads(result)
    if result.get("predictions") != ["setosa"]:
        raise ValueError(f"Smoke prediction failed: {result}")
    if expected_version and result.get("model_version") != expected_version:
        raise ValueError("Endpoint served a different model version")
    return result


def extract_training_archive(archive, destination):
    """Download archives from your own jobs only; reject links and path traversal."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive) as handle:
        for member in handle.getmembers():
            target = (destination / member.name).resolve()
            if not target.is_relative_to(destination.resolve()) or not (
                member.isfile() or member.isdir()
            ):
                raise ValueError("Unsafe training archive member")
        handle.extractall(destination, filter="data")
