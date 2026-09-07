import io
import tarfile
from unittest.mock import MagicMock

import pytest

from iris_mlops.cloud_common import (
    check_prediction,
    extract_training_archive,
    immutable_image,
)


def test_cloud_smoke_checks_identity_and_image_digest():
    with pytest.raises(ValueError, match="different"):
        check_prediction(
            {"predictions": ["setosa"], "model_version": "wrong"}, "expected"
        )
    with pytest.raises(ValueError, match="digest"):
        immutable_image("registry/iris:latest")


def test_training_archive_rejects_traversal(tmp_path):
    path = tmp_path / "unsafe.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        member = tarfile.TarInfo("../escape.txt")
        member.size = 1
        archive.addfile(member, io.BytesIO(b"x"))
    with pytest.raises(ValueError, match="Unsafe"):
        extract_training_archive(path, tmp_path / "output")


def test_aws_pending_model_cannot_allocate_endpoint():
    boto3 = pytest.importorskip("boto3")
    from botocore.stub import Stubber
    from iris_mlops.aws_cloud import deploy

    sm = boto3.client(
        "sagemaker",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    with Stubber(sm) as stub:
        stub.add_response(
            "describe_model_package",
            {
                "ModelPackageName": "test",
                "ModelPackageArn": "arn:aws:sagemaker:us-east-1:123456789012:model-package/test/1",
                "CreationTime": 0,
                "ModelPackageStatus": "Completed",
                "ModelApprovalStatus": "PendingManualApproval",
                "ModelPackageStatusDetails": {"ValidationStatuses": []},
            },
            {"ModelPackageName": "test"},
        )
        with pytest.raises(ValueError, match="Approved"):
            deploy(sm, MagicMock(), "test", "iris-stage", "ml.m5.large")
        stub.assert_no_pending_responses()


def test_azure_staging_does_not_switch_traffic():
    pytest.importorskip("azure.ai.ml")
    from iris_mlops.azure_cloud import deploy

    ml = MagicMock()
    ml.online_endpoints.get.return_value.traffic = {"blue": 100}
    ml.models.get.return_value.id = "azureml:iris-course:1"
    ml.models.get.return_value.tags = {
        "approved": "true",
        "run_id": "baseline",
        "image": "registry/iris@sha256:" + "a" * 64,
    }
    deploy(ml, "iris-endpoint", "green", "1", "Standard_DS3_v2")
    deployment = ml.online_deployments.begin_create_or_update.call_args.args[0]
    assert (
        deployment.environment.inference_config["scoring_route"]["path"]
        == "/invocations"
    )
    assert deployment.model == "azureml:iris-course:1"
    ml.online_endpoints.begin_create_or_update.assert_not_called()
    with pytest.raises(ValueError, match="receiving"):
        deploy(ml, "iris-endpoint", "blue", "2", "Standard_DS3_v2")


def test_azure_training_job_schema(tmp_path):
    pytest.importorskip("azure.ai.ml")
    from azure.ai.ml import load_job
    from iris_mlops.azure_cloud import submit_training
    from iris_mlops.data import prepare_data

    prepare_data(tmp_path / "data")
    ml = MagicMock()
    ml.data.create_or_update.return_value.id = "azureml:iris-snapshot:abc123"
    ml.jobs.create_or_update.return_value.name = "iris-job"
    ml.jobs.get.return_value.status = "Completed"
    submit_training(
        ml, tmp_path / "data", "registry/iris@sha256:" + "a" * 64, "cpu-cluster", 1.0
    )
    # The public command builder is converted to a standalone job by the SDK.
    job = ml.jobs.create_or_update.call_args.args[0]._to_job()
    job.dump(tmp_path / "job.yml")
    loaded = load_job(tmp_path / "job.yml")
    assert loaded.inputs["data"].mode == "download"
    assert loaded.outputs["run"].mode == "upload"
    assert "-m iris_mlops.cloud_train" in loaded.command


def test_aws_training_request_matches_sdk_schema(tmp_path, monkeypatch):
    pytest.importorskip("boto3")
    from botocore.session import Session
    from botocore.validate import validate_parameters
    from iris_mlops.aws_cloud import submit_training
    from iris_mlops.data import prepare_data

    prepare_data(tmp_path / "data")
    monkeypatch.setenv("AWS_BUCKET", "iris-course-test")
    monkeypatch.setenv(
        "AWS_SAGEMAKER_ROLE_ARN", "arn:aws:iam::123456789012:role/iris-course"
    )
    sm, s3 = MagicMock(), MagicMock()
    shape = (
        Session()
        .get_service_model("sagemaker")
        .operation_model("CreateTrainingJob")
        .input_shape
    )
    sm.create_training_job.side_effect = lambda **kwargs: validate_parameters(
        kwargs, shape
    )
    sm.describe_training_job.return_value = {
        "TrainingJobStatus": "Completed",
        "ModelArtifacts": {"S3ModelArtifacts": "s3://iris-course-test/model.tar.gz"},
    }
    submit_training(
        sm,
        s3,
        tmp_path / "data",
        "registry/iris@sha256:" + "a" * 64,
        "iris-course-test",
        "ml.m5.large",
        1.0,
    )
    request = sm.create_training_job.call_args.kwargs
    assert request["InputDataConfig"][0]["ChannelName"] == "training"
    assert request["EnableNetworkIsolation"] is True
    assert s3.upload_file.call_count == 3


def test_azure_endpoint_setup_preserves_existing_traffic():
    pytest.importorskip("azure.ai.ml")
    from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
    from iris_mlops.azure_cloud import create_endpoint

    ml = MagicMock()
    endpoint = ml.online_endpoints.get.return_value
    endpoint.name = "iris-course"
    endpoint.tags = {"course": "iris-mlops"}
    endpoint.auth_mode = "aad_token"
    endpoint.traffic = {"blue": 80, "green": 20}
    assert create_endpoint(ml, "iris-course") == "iris-course"
    assert endpoint.traffic == {"blue": 80, "green": 20}
    ml.online_endpoints.begin_create_or_update.assert_not_called()
    endpoint.tags = {}
    with pytest.raises(ValueError, match="already exists"):
        create_endpoint(ml, "iris-course")
    ml.online_endpoints.get.side_effect = HttpResponseError("Access denied")
    with pytest.raises(HttpResponseError):
        create_endpoint(ml, "iris-course")
    ml.online_endpoints.begin_create_or_update.assert_not_called()
    ml.online_endpoints.get.side_effect = ResourceNotFoundError("Missing")
    create_endpoint(ml, "new-course")
    created = ml.online_endpoints.begin_create_or_update.call_args.args[0]
    assert created.name == "new-course"
    assert created.auth_mode == "aad_token"


@pytest.mark.parametrize("provider", ["azure", "aws"])
def test_mutable_image_is_rejected_before_cloud_writes(provider, tmp_path):
    if provider == "azure":
        pytest.importorskip("azure.ai.ml")
        from iris_mlops.azure_cloud import submit_training

        ml = MagicMock()
        with pytest.raises(ValueError, match="digest"):
            submit_training(ml, tmp_path, "registry/iris:latest", "cpu-cluster", 1)
        assert not ml.mock_calls
    else:
        from iris_mlops.aws_cloud import submit_training

        sm, s3 = MagicMock(), MagicMock()
        with pytest.raises(ValueError, match="digest"):
            submit_training(
                sm, s3, tmp_path, "registry/iris:latest", "job", "ml.m5.large", 1
            )
        assert not sm.mock_calls
        assert not s3.mock_calls


def test_aws_approved_but_incomplete_package_cannot_allocate_endpoint():
    from iris_mlops.aws_cloud import deploy

    sm = MagicMock()
    sm.describe_model_package.return_value = {
        "ModelApprovalStatus": "Approved",
        "ModelPackageStatus": "InProgress",
    }
    with pytest.raises(ValueError, match="Completed"):
        deploy(sm, MagicMock(), "package", "stage", "ml.m5.large")
    sm.create_model.assert_not_called()
    sm.create_endpoint_config.assert_not_called()
    sm.create_endpoint.assert_not_called()
