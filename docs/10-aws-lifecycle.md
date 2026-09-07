# Lesson 10: Train, approve, and operate on AWS

**Goal:** repeat the complete release cycle with SageMaker AI. Keep the AWS
variables from lesson 09 set. Run Python commands from `python/`.

## 1. Run a managed training job

```bash
uv run --extra aws iris-aws train --name iris-course-train-v1 --image "$AWS_IMAGE"
uv run --extra aws iris-aws download --name iris-course-train-v1 \
  --output downloads/aws-v1
```

Use unique training job names on subsequent runs. The adapter validates data,
uploads it to a hash-based S3 prefix, and creates a CPU training job. SageMaker
mounts the channel under `/opt/ml/input/data/training`, invokes the container's
`train` command, and uploads `/opt/ml/model` as a compressed artifact. Network
isolation is enabled; the runtime already contains its dependencies. Inspect
job logs in `/aws/sagemaker/TrainingJobs` and the job's input/output paths.
See the [training API](https://docs.aws.amazon.com/boto3/latest/reference/services/sagemaker/client/create_training_job.html)
and [container training information](https://docs.aws.amazon.com/sagemaker/latest/dg/your-algorithms-training-algo-running-container.html).

The downloaded candidate includes Iris snapshots for this lesson's audit trail;
the subsequent production export excludes them. It has not been approved merely
because training completed.

## 2. Review locally, then create a pending registry version

```bash
AWS_RUN=$(uv run iris import downloads/aws-v1)
export AWS_RUN_V1="$AWS_RUN"
uv run iris evaluate "$AWS_RUN"
uv run iris promote "$AWS_RUN"
uv run iris export "$AWS_RUN" --output "releases/$AWS_RUN"
AWS_PACKAGE=$(uv run --extra aws iris-aws register --bundle "releases/$AWS_RUN" --image "$AWS_IMAGE")
echo "$AWS_PACKAGE"
```

The shell variable `AWS_PACKAGE` contains the printed model package ARN. The exact release archive is uploaded to S3;
the package records its model checksum, release checksum, run ID and image.
It starts with native status `PendingManualApproval`, even though the local
review has passed. In SageMaker's Model Registry, inspect the version before
approving it:

```bash
uv run --extra aws iris-aws approve --package "$AWS_PACKAGE" --bundle "releases/$AWS_RUN"
```

Approval verifies that the registry metadata matches the local release. This
demonstrates [SageMaker package approval](https://docs.aws.amazon.com/boto3/latest/reference/services/sagemaker/client/create_model_package.html).
Keep the same local registry across the labs so evaluation sees the incumbent.
In a team workflow, synchronize that incumbent with the target environment before
review; a fresh empty local registry cannot assess regression against production.

## 3. Stage and promote

```bash
uv run --extra aws iris-aws deploy --package "$AWS_PACKAGE" --name iris-course-stage-v1
uv run --extra aws iris-aws smoke --endpoint iris-course-stage-v1
uv run --extra aws iris-aws promote --staging iris-course-stage-v1 --production iris-course-prod
uv run --extra aws iris-aws smoke --endpoint iris-course-prod
uv run --extra aws iris-aws status --endpoint iris-course-prod
```

Deployment requires a package with `Approved` approval and `Completed` creation
status. If it is still processing, inspect its registry status and retry after
completion. It creates a native model,
an endpoint configuration and a staging endpoint, all with the supplied name.
The package supplies both model archive and image. The API is invoked with
IAM-signed requests through `sagemaker-runtime`; there is no public unauthenticated
URL to curl. See the [model API](https://docs.aws.amazon.com/boto3/latest/reference/services/sagemaker/client/create_model.html).

Promotion smoke-tests staging, records the old configuration in `state/`, and
creates or updates the separate production endpoint with that exact configuration.
The waiter verifies `InService`, then a smoke test checks the served version.
An update is asynchronous and is not an instantaneous local pointer change.

## 4. Update and recover

Reuse the tested image and train a second candidate locally; step 1 already
covered managed training. Inspect each report and the pending package before the
next approval. Use fresh stage names when repeating the lab:

```bash
AWS_RUN_V2=$(uv run iris train --C 10)
uv run iris evaluate "$AWS_RUN_V2"
uv run iris promote "$AWS_RUN_V2"
uv run iris export "$AWS_RUN_V2" --output "releases/$AWS_RUN_V2"
AWS_PACKAGE_V2=$(uv run --extra aws iris-aws register \
  --bundle "releases/$AWS_RUN_V2" --image "$AWS_IMAGE")
echo "$AWS_PACKAGE_V2"
```

Inspect that version in the registry. Then approve and stage it:

```bash
uv run --extra aws iris-aws approve --package "$AWS_PACKAGE_V2" \
  --bundle "releases/$AWS_RUN_V2"
uv run --extra aws iris-aws deploy --package "$AWS_PACKAGE_V2" --name iris-course-stage-v2
uv run --extra aws iris-aws smoke --endpoint iris-course-stage-v2
```

Switch production, then practice recovery:

```bash
uv run --extra aws iris-aws promote --staging iris-course-stage-v2 --production iris-course-prod
uv run --extra aws iris-aws rollback --endpoint iris-course-prod --config iris-course-stage-v1
```

After rollback, align the local approval pointer and verify the served version:

```bash
uv run --extra aws iris-aws smoke --endpoint iris-course-prod
uv run iris rollback "$AWS_RUN_V1"
```

Rollback uses the previous endpoint configuration, verifies its package is still
approved, waits for service and smoke-tests it. Keep the old config, model,
package, artifact and image. If an update or smoke test fails, inspect status
and `state/aws-switch-iris-course-prod.json`, then explicitly restore the previous
config. The provided release script does not wire automatic rollback alarms.
For that extension, study [deployment guardrails](https://docs.aws.amazon.com/sagemaker/latest/dg/deployment-guardrails.html).

You can delete staging endpoints after release while retaining their configs and
models for rollback. Do not delete a retained config just because its original
staging endpoint is gone.

## 5. Observe service and model behavior

SageMaker sends container stdout to `/aws/sagemaker/Endpoints/ENDPOINT_NAME`.
In CloudWatch, set a short log retention for each course group and inspect the
queries in `cloud/aws/monitoring.txt`. Chart `ModelLatency`, invocations and
5xx errors in `AWS/SageMaker`, using endpoint and variant dimensions. SageMaker
platform latency is in microseconds; our application log field is milliseconds.
See [endpoint monitoring](https://docs.aws.amazon.com/sagemaker/latest/dg/manage-endpoints-console-monitoring.html)
and [endpoint metric details](https://aws.amazon.com/blogs/machine-learning/enhanced-metrics-for-amazon-sagemaker-ai-endpoints-deeper-visibility-for-better-performance/).

Create a small lab alarm (visible in CloudWatch; attach an SNS notification
target you control in the console if desired):

```bash
aws cloudwatch put-metric-alarm --alarm-name iris-course-prod-5xx \
  --namespace AWS/SageMaker --metric-name Invocation5XXErrors \
  --dimensions Name=EndpointName,Value=iris-course-prod Name=VariantName,Value=AllTraffic \
  --statistic Sum --period 300 --evaluation-periods 1 --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold --treat-missing-data notBreaching
```

For real traffic, use a rate with minimum volume, choose a latency objective from
measurements, and test alert delivery. This alarm is not automatically attached
to an endpoint update policy.

Export console messages and reuse local monitoring:

```bash
aws logs filter-log-events --log-group-name /aws/sagemaker/Endpoints/iris-course-prod \
  --filter-pattern '"prediction"' --query 'events[].message' --output json > state/aws-messages.json
uv run iris-logs state/aws-messages.json state/aws-predictions.jsonl
uv run iris-monitor --bundle "releases/$AWS_RUN_V1" --log state/aws-predictions.jsonl
```

For scheduled monitoring, add `--start-time`/`--end-time` epoch milliseconds for
a defined window. Supply a release matching the served version and add independent
feedback when available. The normalization script deduplicates repeated exported
events. Unknown accuracy stays `null`; smoke calls alone are too few for drift.

The endpoint config also enables input/output capture to `s3://$AWS_BUCKET/course/capture`.
Its platform envelope differs from our JSONL format; use the console-log export
above for the shared script. Inspect one capture record and locate its payloads
as an exercise. For production, evaluate SageMaker Model Monitor or a scheduled
processing job, and define sampling, retention, label joins and alert ownership.
See [data capture configuration](https://docs.aws.amazon.com/boto3/latest/reference/services/sagemaker/client/create_endpoint_config.html).

## 6. Clean up everything created by the lab

Record the endpoint configuration/model names and package ARNs before deleting
anything. From `python/`, list **all** names you actually created:

```bash
uv run --extra aws iris-cleanup-aws --stack iris-course \
  --endpoint iris-course-stage-v1 --endpoint iris-course-stage-v2 --endpoint iris-course-prod \
  --config iris-course-stage-v1 --config iris-course-stage-v2 \
  --model iris-course-stage-v1 --model iris-course-stage-v2 --purge-storage
aws cloudwatch delete-alarms --alarm-names iris-course-prod-5xx
```

Omit v2 names if you did not create them. The helper tolerates already-deleted
named endpoints, removes the listed configs/models, deletes package versions
in the dedicated stack's group, and deletes the stack. `--purge-storage` also
permanently removes all object versions/delete markers in its retained S3 bucket
and all images in its retained ECR repository. Omit that flag to preserve data,
but budget for the retained resources. Never point this helper at shared resources.

Training job records remain as service history. Remove the course endpoint log
groups and, if dedicated to the lab, `/aws/sagemaker/TrainingJobs` in CloudWatch
after saving evidence. Delete any SNS resources you added. Verify SageMaker has
no course endpoints left and check Cost Explorer after billing catches up.

**Done when:** a pending package is prevented from deploying, an approved model
serves from production, rollback restores v1, monitoring shows the right version,
and all billable lab resources are removed or explicitly retained.

Next: [capstone and operations](11-capstone-and-operations.md).
