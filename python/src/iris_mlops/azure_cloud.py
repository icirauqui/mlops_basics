"""Azure ML jobs, model versions, staged endpoints, and traffic promotion."""

import argparse
import hashlib
import json
import os
from pathlib import Path

from iris_mlops.cloud_common import check_prediction, immutable_image
from iris_mlops.data import DATA_DIR, SPLITS, sha256, validate_data
from iris_mlops.workflow import BASE_DIR, now, verify_bundle, write_json


def client():
    from azure.ai.ml import MLClient
    from azure.identity import DefaultAzureCredential

    return MLClient(
        DefaultAzureCredential(),
        os.environ["AZURE_SUBSCRIPTION_ID"],
        os.environ["AZURE_RESOURCE_GROUP"],
        os.environ["AZURE_ML_WORKSPACE"],
    )


def submit_training(ml, data_dir, image, compute, C):
    from azure.ai.ml import Input, Output, command
    from azure.ai.ml.entities import Data, Environment

    image = immutable_image(image)
    validate_data(data_dir)
    digest = hashlib.sha256(
        "".join(sha256(Path(data_dir) / f"{split}.csv") for split in SPLITS).encode()
    ).hexdigest()[:16]
    asset = ml.data.create_or_update(
        Data(
            name="iris-snapshot",
            version=digest,
            path=str(data_dir),
            type="uri_folder",
            description="Fixed Iris train/validation/test CSVs",
        )
    )
    job = command(
        experiment_name="iris-course",
        display_name="iris-logistic-regression",
        command='python -m iris_mlops.cloud_train --data "${{inputs.data}}" --output "${{outputs.run}}" --C ${{inputs.c}}',
        environment=Environment(image=image),
        compute=compute,
        inputs={
            "data": Input(type="uri_folder", path=asset.id, mode="download"),
            "c": C,
        },
        outputs={"run": Output(type="uri_folder", mode="upload")},
        tags={"course": "iris-mlops", "data_version": digest},
    )
    created = ml.jobs.create_or_update(job)
    print(f"Submitted job: {created.name}", flush=True)
    ml.jobs.stream(created.name)
    if ml.jobs.get(created.name).status != "Completed":
        raise RuntimeError("Training did not complete; inspect the job logs")
    return created.name


def register_model(ml, bundle, version, image):
    from azure.ai.ml.entities import Model

    metadata = verify_bundle(bundle)
    model = ml.models.create_or_update(
        Model(
            name="iris-course",
            version=version,
            path=str(bundle),
            type="custom_model",
            description="Locally reviewed Iris release",
            tags={
                "approved": "true",
                "run_id": metadata["run_id"],
                "model_sha256": metadata["model_sha256"],
                "image": immutable_image(image),
            },
        )
    )
    return model.id


def create_endpoint(ml, name):
    """Resume setup without replacing an existing endpoint or its traffic."""
    from azure.ai.ml.entities import ManagedOnlineEndpoint
    from azure.core.exceptions import ResourceNotFoundError

    try:
        existing = ml.online_endpoints.get(name)
    except ResourceNotFoundError:
        return (
            ml.online_endpoints.begin_create_or_update(
                ManagedOnlineEndpoint(
                    name=name, auth_mode="aad_token", tags={"course": "iris-mlops"}
                )
            )
            .result()
            .name
        )
    if (existing.tags or {}).get(
        "course"
    ) != "iris-mlops" or existing.auth_mode != "aad_token":
        raise ValueError(
            "Endpoint already exists with different ownership or authentication; choose a new name"
        )
    return existing.name


def deploy(ml, endpoint, deployment, version, instance_type):
    from azure.ai.ml.entities import Environment, ManagedOnlineDeployment

    if (ml.online_endpoints.get(endpoint).traffic or {}).get(deployment, 0) > 0:
        raise ValueError(
            "Use a new deployment name; this deployment is receiving production traffic"
        )
    model = ml.models.get("iris-course", version=version)
    if model.tags.get("approved") != "true":
        raise ValueError("Model has not been approved")
    environment = Environment(
        image=immutable_image(model.tags["image"]),
        inference_config={
            "liveness_route": {"port": 8080, "path": "/ping"},
            "readiness_route": {"port": 8080, "path": "/ping"},
            "scoring_route": {"port": 8080, "path": "/invocations"},
        },
    )
    created = ml.online_deployments.begin_create_or_update(
        ManagedOnlineDeployment(
            name=deployment,
            endpoint_name=endpoint,
            model=model.id,
            environment=environment,
            model_mount_path="/models",
            environment_variables={"MODEL_DIR": "/models"},
            instance_type=instance_type,
            instance_count=1,
            tags={"run_id": model.tags["run_id"], "approved": "true"},
        )
    ).result()
    # No traffic mutation: explicitly invoke this deployment before switching.
    return {"deployment": created.name, "state": created.provisioning_state}


def smoke(ml, endpoint, deployment=None):
    version = (
        ml.online_deployments.get(deployment, endpoint).tags["run_id"]
        if deployment
        else None
    )
    return check_prediction(
        ml.online_endpoints.invoke(
            endpoint_name=endpoint,
            deployment_name=deployment,
            request_file=str(BASE_DIR / "examples" / "sample-request.json"),
        ),
        version,
    )


def switch(ml, endpoint, deployment):
    target = ml.online_deployments.get(deployment, endpoint)
    if target.tags.get("approved") != "true":
        raise ValueError("Deployment is not approved")
    smoke(ml, endpoint, deployment)
    resource = ml.online_endpoints.get(endpoint)
    receipt = {
        "at": now(),
        "endpoint": endpoint,
        "previous_traffic": resource.traffic,
        "new_traffic": {deployment: 100},
    }
    write_json(BASE_DIR / "state" / f"azure-switch-{endpoint}.json", receipt)
    resource.traffic = {deployment: 100}
    ml.online_endpoints.begin_create_or_update(resource).result()
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    training = commands.add_parser("train")
    training.add_argument("--data", type=Path, default=DATA_DIR)
    training.add_argument("--image", required=True)
    training.add_argument("--compute", default="cpu-cluster")
    training.add_argument("--C", type=float, default=1.0)
    download = commands.add_parser("download")
    download.add_argument("job")
    download.add_argument("--output", default="downloads/azure")
    register = commands.add_parser("register")
    register.add_argument("--bundle", type=Path, required=True)
    register.add_argument("--version", required=True)
    register.add_argument("--image", required=True)
    for action in [
        "create-endpoint",
        "deploy",
        "smoke",
        "switch",
        "status",
        "logs",
        "delete-endpoint",
    ]:
        command_parser = commands.add_parser(action)
        command_parser.add_argument("--endpoint", required=True)
        if action in ["deploy", "switch", "logs"]:
            command_parser.add_argument("--deployment", required=True)
        if action == "smoke":
            command_parser.add_argument("--deployment")
        if action == "deploy":
            command_parser.add_argument("--version", required=True)
            command_parser.add_argument("--instance-type", default="Standard_DS3_v2")
    args = parser.parse_args()
    ml = client()
    if args.action == "train":
        result = submit_training(ml, args.data, args.image, args.compute, args.C)
    elif args.action == "download":
        ml.jobs.download(args.job, download_path=args.output, output_name="run")
        result = [str(path.parent) for path in Path(args.output).rglob("run.json")]
    elif args.action == "register":
        result = register_model(ml, args.bundle, args.version, args.image)
    elif args.action == "create-endpoint":
        result = create_endpoint(ml, args.endpoint)
    elif args.action == "deploy":
        result = deploy(
            ml, args.endpoint, args.deployment, args.version, args.instance_type
        )
    elif args.action == "smoke":
        result = smoke(ml, args.endpoint, args.deployment)
    elif args.action == "switch":
        result = switch(ml, args.endpoint, args.deployment)
    elif args.action == "status":
        endpoint = ml.online_endpoints.get(args.endpoint)
        result = {
            "endpoint": endpoint.name,
            "traffic": endpoint.traffic,
            "state": endpoint.provisioning_state,
            "scoring_uri": endpoint.scoring_uri,
        }
    elif args.action == "logs":
        result = ml.online_deployments.get_logs(
            args.deployment, args.endpoint, lines=200
        )
    else:
        ml.online_endpoints.begin_delete(args.endpoint).result()
        result = "Endpoint and its deployments deleted"
    print(
        result if isinstance(result, str) else json.dumps(result, indent=2, default=str)
    )


if __name__ == "__main__":
    main()
