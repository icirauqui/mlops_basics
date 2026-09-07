"""SageMaker AI training, registry approval, staging, promotion, and rollback."""

import argparse
import hashlib
import json
import os
import tarfile
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from iris_mlops.cloud_common import (
    SAMPLE,
    check_prediction,
    extract_training_archive,
    immutable_image,
)
from iris_mlops.data import DATA_DIR, SPLITS, sha256, validate_data
from iris_mlops.workflow import BASE_DIR, BUNDLE_FILES, now, verify_bundle, write_json


def clients():
    import boto3

    session = boto3.Session(region_name=os.environ["AWS_REGION"])
    return (
        session.client("sagemaker"),
        session.client("s3"),
        session.client("sagemaker-runtime"),
    )


def submit_training(sm, s3, data_dir, image, name, instance_type, C):
    image = immutable_image(image)
    validate_data(data_dir)
    bucket = os.environ["AWS_BUCKET"]
    digest = hashlib.sha256(
        "".join(sha256(Path(data_dir) / f"{split}.csv") for split in SPLITS).encode()
    ).hexdigest()
    prefix = f"course/data/{digest}"
    for split in SPLITS:
        s3.upload_file(
            str(Path(data_dir) / f"{split}.csv"), bucket, f"{prefix}/{split}.csv"
        )
    sm.create_training_job(
        TrainingJobName=name,
        AlgorithmSpecification={
            "TrainingImage": image,
            "TrainingInputMode": "File",
        },
        RoleArn=os.environ["AWS_SAGEMAKER_ROLE_ARN"],
        InputDataConfig=[
            {
                "ChannelName": "training",
                "DataSource": {
                    "S3DataSource": {
                        "S3DataType": "S3Prefix",
                        "S3Uri": f"s3://{bucket}/{prefix}/",
                        "S3DataDistributionType": "FullyReplicated",
                    }
                },
            }
        ],
        OutputDataConfig={"S3OutputPath": f"s3://{bucket}/course/training"},
        ResourceConfig={
            "InstanceType": instance_type,
            "InstanceCount": 1,
            "VolumeSizeInGB": 10,
        },
        StoppingCondition={"MaxRuntimeInSeconds": 1800},
        HyperParameters={"C": str(C)},
        EnableNetworkIsolation=True,
        Tags=[{"Key": "course", "Value": "iris-mlops"}],
    )
    print(f"Submitted training job: {name}", flush=True)
    sm.get_waiter("training_job_completed_or_stopped").wait(
        TrainingJobName=name, WaiterConfig={"Delay": 20, "MaxAttempts": 180}
    )
    result = sm.describe_training_job(TrainingJobName=name)
    if result["TrainingJobStatus"] != "Completed":
        raise RuntimeError("Training stopped without completing")
    return result["ModelArtifacts"]["S3ModelArtifacts"]


def download_training(sm, s3, name, output):
    result = sm.describe_training_job(TrainingJobName=name)
    if result["TrainingJobStatus"] != "Completed":
        raise ValueError("Training has not completed")
    uri = urlparse(result["ModelArtifacts"]["S3ModelArtifacts"])
    with tempfile.TemporaryDirectory() as temporary:
        archive = Path(temporary) / "model.tar.gz"
        s3.download_file(uri.netloc, uri.path.lstrip("/"), str(archive))
        extract_training_archive(archive, output)
    return str(output)


def register_model(sm, s3, bundle, image):
    metadata = verify_bundle(bundle)
    image = immutable_image(image)
    bucket = os.environ["AWS_BUCKET"]
    release_hash = sha256(Path(bundle) / "release.json")
    key = f"course/releases/{metadata['run_id']}/{release_hash}/model.tar.gz"
    with tempfile.TemporaryDirectory() as temporary:
        archive = Path(temporary) / "model.tar.gz"
        with tarfile.open(archive, "w:gz") as handle:
            for name in BUNDLE_FILES:
                handle.add(Path(bundle) / name, arcname=name)
        s3.upload_file(str(archive), bucket, key)
    result = sm.create_model_package(
        ModelPackageGroupName=os.environ["AWS_MODEL_PACKAGE_GROUP"],
        ModelPackageDescription=f"Iris run {metadata['run_id']}",
        ModelApprovalStatus="PendingManualApproval",
        CustomerMetadataProperties={
            "run_id": metadata["run_id"],
            "model_sha256": metadata["model_sha256"],
            "release_sha256": release_hash,
        },
        InferenceSpecification={
            "Containers": [{"Image": image, "ModelDataUrl": f"s3://{bucket}/{key}"}],
            "SupportedContentTypes": ["application/json"],
            "SupportedResponseMIMETypes": ["application/json"],
        },
    )
    return result["ModelPackageArn"]


def approve(sm, package, bundle):
    metadata = verify_bundle(bundle)
    remote = sm.describe_model_package(ModelPackageName=package)[
        "CustomerMetadataProperties"
    ]
    if (
        remote["model_sha256"] != metadata["model_sha256"]
        or remote["run_id"] != metadata["run_id"]
        or remote["release_sha256"] != sha256(Path(bundle) / "release.json")
    ):
        raise ValueError("Package does not match the reviewed local release")
    sm.update_model_package(
        ModelPackageArn=package,
        ModelApprovalStatus="Approved",
        ApprovalDescription="Reviewed local validation gate and release checksums",
    )
    return package


def approved_package(sm, package):
    description = sm.describe_model_package(ModelPackageName=package)
    if description["ModelApprovalStatus"] != "Approved":
        raise ValueError("Only Approved registry packages can be deployed")
    if description["ModelPackageStatus"] != "Completed":
        raise ValueError(
            "Model package is not Completed; inspect its status before retrying"
        )
    return description["CustomerMetadataProperties"]["run_id"]


def approved_config(sm, config):
    description = sm.describe_endpoint_config(EndpointConfigName=config)
    if len(description["ProductionVariants"]) != 1:
        raise ValueError("This lesson supports exactly one model per endpoint config")
    model = sm.describe_model(
        ModelName=description["ProductionVariants"][0]["ModelName"]
    )
    return approved_package(sm, model["PrimaryContainer"]["ModelPackageName"])


def wait_endpoint(sm, endpoint):
    sm.get_waiter("endpoint_in_service").wait(
        EndpointName=endpoint, WaiterConfig={"Delay": 20, "MaxAttempts": 180}
    )


def smoke(sm, runtime, endpoint):
    config = sm.describe_endpoint(EndpointName=endpoint)["EndpointConfigName"]
    version = approved_config(sm, config)
    result = runtime.invoke_endpoint(
        EndpointName=endpoint,
        ContentType="application/json",
        Body=json.dumps(SAMPLE).encode(),
    )
    return check_prediction(result["Body"].read(), version)


def deploy(sm, runtime, package, name, instance_type):
    approved_package(sm, package)
    sm.create_model(
        ModelName=name,
        ExecutionRoleArn=os.environ["AWS_SAGEMAKER_ROLE_ARN"],
        PrimaryContainer={"ModelPackageName": package},
        EnableNetworkIsolation=True,
    )
    sm.create_endpoint_config(
        EndpointConfigName=name,
        ProductionVariants=[
            {
                "VariantName": "AllTraffic",
                "ModelName": name,
                "InitialInstanceCount": 1,
                "InstanceType": instance_type,
                "InitialVariantWeight": 1.0,
            }
        ],
        DataCaptureConfig={
            "EnableCapture": True,
            "InitialSamplingPercentage": 100,
            "DestinationS3Uri": f"s3://{os.environ['AWS_BUCKET']}/course/capture",
            "CaptureOptions": [{"CaptureMode": "Input"}, {"CaptureMode": "Output"}],
            "CaptureContentTypeHeader": {"JsonContentTypes": ["application/json"]},
        },
    )
    sm.create_endpoint(
        EndpointName=name,
        EndpointConfigName=name,
        Tags=[{"Key": "course", "Value": "iris-mlops"}],
    )
    wait_endpoint(sm, name)
    return smoke(sm, runtime, name)


def promote(sm, runtime, staging, production):
    from botocore.exceptions import ClientError

    smoke(sm, runtime, staging)
    config = sm.describe_endpoint(EndpointName=staging)["EndpointConfigName"]
    try:
        previous = sm.describe_endpoint(EndpointName=production)["EndpointConfigName"]
    except ClientError as error:
        # Do not turn access errors or unrelated validation failures into creates.
        if error.response["Error"][
            "Code"
        ] != "ValidationException" or "Could not find" not in str(error):
            raise
        previous = None
    receipt = {
        "at": now(),
        "endpoint": production,
        "previous_config": previous,
        "new_config": config,
    }
    write_json(BASE_DIR / "state" / f"aws-switch-{production}.json", receipt)
    if previous:
        sm.update_endpoint(EndpointName=production, EndpointConfigName=config)
    else:
        sm.create_endpoint(
            EndpointName=production,
            EndpointConfigName=config,
            Tags=[{"Key": "course", "Value": "iris-mlops"}],
        )
    wait_endpoint(sm, production)
    smoke(sm, runtime, production)
    return receipt


def rollback(sm, runtime, endpoint, config):
    approved_config(sm, config)
    sm.update_endpoint(EndpointName=endpoint, EndpointConfigName=config)
    wait_endpoint(sm, endpoint)
    return smoke(sm, runtime, endpoint)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    training = commands.add_parser("train")
    training.add_argument("--data", type=Path, default=DATA_DIR)
    training.add_argument("--image", required=True)
    training.add_argument("--name", required=True)
    training.add_argument("--instance-type", default="ml.m5.large")
    training.add_argument("--C", type=float, default=1.0)
    download = commands.add_parser("download")
    download.add_argument("--name", required=True)
    download.add_argument("--output", type=Path, required=True)
    register = commands.add_parser("register")
    register.add_argument("--bundle", type=Path, required=True)
    register.add_argument("--image", required=True)
    approval = commands.add_parser("approve")
    approval.add_argument("--package", required=True)
    approval.add_argument("--bundle", type=Path, required=True)
    deployment = commands.add_parser("deploy")
    deployment.add_argument("--package", required=True)
    deployment.add_argument("--name", required=True)
    deployment.add_argument("--instance-type", default="ml.m5.large")
    promotion = commands.add_parser("promote")
    promotion.add_argument("--staging", required=True)
    promotion.add_argument("--production", required=True)
    for action in ["smoke", "status", "rollback", "delete-endpoint"]:
        command = commands.add_parser(action)
        command.add_argument("--endpoint", required=True)
        if action == "rollback":
            command.add_argument("--config", required=True)
    args = parser.parse_args()
    sm, s3, runtime = clients()
    if args.action == "train":
        result = submit_training(
            sm, s3, args.data, args.image, args.name, args.instance_type, args.C
        )
    elif args.action == "download":
        result = download_training(sm, s3, args.name, args.output)
    elif args.action == "register":
        result = register_model(sm, s3, args.bundle, args.image)
    elif args.action == "approve":
        result = approve(sm, args.package, args.bundle)
    elif args.action == "deploy":
        result = deploy(sm, runtime, args.package, args.name, args.instance_type)
    elif args.action == "promote":
        result = promote(sm, runtime, args.staging, args.production)
    elif args.action == "rollback":
        result = rollback(sm, runtime, args.endpoint, args.config)
    elif args.action == "smoke":
        result = smoke(sm, runtime, args.endpoint)
    elif args.action == "status":
        result = sm.describe_endpoint(EndpointName=args.endpoint)
    else:
        sm.delete_endpoint(EndpointName=args.endpoint)
        sm.get_waiter("endpoint_deleted").wait(EndpointName=args.endpoint)
        result = (
            "Endpoint deleted; retain configs/models until rollback is no longer needed"
        )
    print(
        result if isinstance(result, str) else json.dumps(result, indent=2, default=str)
    )


if __name__ == "__main__":
    main()
