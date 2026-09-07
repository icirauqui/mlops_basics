"""Stable workspace paths for editable installs, notebooks, and the container."""

import os
from pathlib import Path

# uv installs this project editably from src/. The container sets its workspace
# explicitly because it installs a regular wheel into site-packages instead.
PROJECT_DIR = Path(
    os.environ.get("IRIS_WORKSPACE", Path(__file__).resolve().parents[2])
).resolve()
