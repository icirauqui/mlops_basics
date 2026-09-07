"""Delete explicitly listed course resources; optionally purge retained storage."""

import argparse
import os


def main():
    import boto3
    from botocore.exceptions import ClientError

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stack", required=True)
    for resource in ["endpoint", "config", "model"]:
        parser.add_argument(f"--{resource}", action="append", default=[])
    parser.add_argument(
        "--purge-storage",
        action="store_true",
        help="Permanently delete all versions in the stack bucket and all stack ECR images",
    )
    args = parser.parse_args()
    session = boto3.Session(region_name=os.environ["AWS_REGION"])
    sm, cf = session.client("sagemaker"), session.client("cloudformation")
    stack = cf.describe_stacks(StackName=args.stack)["Stacks"][0]
    outputs = {item["OutputKey"]: item["OutputValue"] for item in stack["Outputs"]}

    def if_present(function, **kwargs):
        try:
            return function(**kwargs)
        except ClientError as error:
            code = error.response["Error"]["Code"]
            if code == "ValidationException" and "Could not find" in str(error):
                return None
            raise

    for name in args.endpoint:
        if if_present(sm.describe_endpoint, EndpointName=name):
            sm.delete_endpoint(EndpointName=name)
            sm.get_waiter("endpoint_deleted").wait(EndpointName=name)
    for name in args.config:
        if_present(sm.delete_endpoint_config, EndpointConfigName=name)
    for name in args.model:
        if_present(sm.delete_model, ModelName=name)
    for page in sm.get_paginator("list_model_packages").paginate(
        ModelPackageGroupName=outputs["ModelPackageGroup"]
    ):
        for package in page["ModelPackageSummaryList"]:
            sm.delete_model_package(ModelPackageName=package["ModelPackageArn"])
    # Delete retained storage before the stack, so a failed purge leaves discoverable outputs.
    if args.purge_storage:
        bucket = session.resource("s3").Bucket(outputs["Bucket"])
        bucket.object_versions.delete()
        bucket.delete()
        session.client("ecr").delete_repository(
            repositoryName=outputs["RepositoryName"], force=True
        )
    cf.delete_stack(StackName=args.stack)
    cf.get_waiter("stack_delete_complete").wait(StackName=args.stack)
    print(
        "Stack deleted. Inspect CloudWatch alarms/log groups and billing as described in lesson 10."
    )
    if not args.purge_storage:
        print(
            f"Retained S3 bucket: {outputs['Bucket']}; ECR repository: {outputs['RepositoryName']}"
        )


if __name__ == "__main__":
    main()
