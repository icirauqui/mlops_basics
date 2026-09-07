"""Test managed-container training and both cloud model-mount conventions locally."""

import argparse
import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from iris_mlops.cloud_common import SAMPLE, check_prediction
from iris_mlops.data import prepare_data
from iris_mlops.workflow import BASE_DIR, export_bundle, import_run, promote


def docker(*arguments, capture=False):
    return subprocess.run(
        ["docker", *map(str, arguments)], check=True, text=True, capture_output=capture
    ).stdout


def smoke_container(image, bundle, version, azure=False):
    name = "iris-check-" + uuid.uuid4().hex[:10]
    mount = "/models/iris/1" if azure else "/opt/ml/model"
    arguments = [
        "run",
        "-d",
        "--rm",
        "--name",
        name,
        "-p",
        "127.0.0.1::8080",
        "--mount",
        f"type=bind,src={bundle},dst={mount},readonly",
    ]
    if azure:
        arguments.extend(["-e", "MODEL_DIR=/models"])
    docker(*arguments, image, "serve", capture=True)
    try:
        address = docker("port", name, "8080", capture=True).strip()
        url = f"http://{address}"
        for attempt in range(60):
            try:
                with urllib.request.urlopen(url + "/ping", timeout=2) as response:
                    assert json.load(response)["model_version"] == version
                break
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                if attempt == 59:
                    raise
                time.sleep(1)
        request = urllib.request.Request(
            url + "/invocations",
            data=json.dumps(SAMPLE).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            check_prediction(json.load(response), version)
        invalid = urllib.request.Request(
            url + "/invocations",
            data=b'{"instances": []}',
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(invalid, timeout=10)
        except urllib.error.HTTPError as error:
            assert error.code == 422
        else:
            raise AssertionError("Malformed request should have failed")
    except Exception:
        docker("logs", name)
        raise
    finally:
        docker("stop", name, capture=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="iris-course:v1")
    args = parser.parse_args()
    scratch = BASE_DIR / "state" / "container-checks"
    scratch.mkdir(parents=True, exist_ok=True)
    # Some Docker installations have a different /tmp namespace from the client.
    with tempfile.TemporaryDirectory(dir=scratch) as temporary:
        work = Path(temporary)
        data, candidate = work / "data", work / "candidate"
        prepare_data(data)
        candidate.mkdir()
        docker(
            "run",
            "--rm",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--mount",
            f"type=bind,src={data},dst=/opt/ml/input/data/training,readonly",
            "--mount",
            f"type=bind,src={candidate},dst=/opt/ml/model",
            args.image,
            "train",
        )
        root = work / "state"
        version = import_run(candidate, root)
        promote(version, root)
        bundle = export_bundle(version, work / "release", root)
        for azure in [False, True]:
            smoke_container(args.image, bundle, version, azure)
        print(
            "Verified container training, approval/export, both cloud mounts, versioned inference and HTTP validation."
        )


if __name__ == "__main__":
    main()
