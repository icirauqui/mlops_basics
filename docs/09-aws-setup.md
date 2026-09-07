# Lesson 09: Prepare Amazon SageMaker AI

**Goal:** provision the few resources needed to train and host the same container
on AWS. A SageMaker Studio domain and Amazon Bedrock are not required: the local
notebooks submit jobs through boto3. Complete local Docker testing first.

## Resources and permissions

`cloud/aws/resources.yml` creates a private, encrypted, versioned S3 bucket; an
ECR image repository with immutable tags; a SageMaker model package group; and
an execution role for SageMaker. The role can access the course bucket prefix,
pull from the course repository and write service logs. It does not grant the
human operator permissions. See [SageMaker prerequisites](https://docs.aws.amazon.com/sagemaker/latest/dg/gs-set-up.html)
and the [model package group resource](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-sagemaker-modelpackagegroup.html).

Use an AWS sandbox account and a short-lived identity, preferably IAM Identity
Center/SSO. The setup operator needs CloudFormation, IAM role/policy creation,
S3, ECR and SageMaker registry permissions. The lab operator also needs to submit
and inspect jobs, manage/invoke endpoints, read logs, upload/download course
objects and `iam:PassRole` restricted to the stack's execution role with
`iam:PassedToService = sagemaker.amazonaws.com`. Ask your administrator to scope
these permissions to the lab resources. The execution role is assumed by
SageMaker, not used as your local login.

## Deploy the infrastructure template

Install [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).
From the repository root:

```bash
aws configure sso
export AWS_PROFILE='your-sso-profile'
aws sso login --profile "$AWS_PROFILE"
export AWS_REGION='eu-west-1'
export AWS_DEFAULT_REGION="$AWS_REGION"
aws sts get-caller-identity
aws cloudformation deploy --template-file cloud/aws/resources.yml \
  --stack-name iris-course --capabilities CAPABILITY_IAM
aws cloudformation describe-stacks --stack-name iris-course --query 'Stacks[0].Outputs'
```

Choose a region with quota for `ml.m5.large` training and real-time endpoint
instances; quota for those uses is separate and new accounts may start at zero.
The instance type is an example, not a guarantee of availability. Use Service
Quotas to request capacity or pass `--instance-type` with a supported CPU type.

Read the stack outputs into your terminal variables:

```bash
export AWS_BUCKET=$(aws cloudformation describe-stacks --stack-name iris-course \
  --query "Stacks[0].Outputs[?OutputKey=='Bucket'].OutputValue | [0]" --output text)
export AWS_ECR_URI=$(aws cloudformation describe-stacks --stack-name iris-course \
  --query "Stacks[0].Outputs[?OutputKey=='RepositoryUri'].OutputValue | [0]" --output text)
export AWS_ECR_REPOSITORY=$(aws cloudformation describe-stacks --stack-name iris-course \
  --query "Stacks[0].Outputs[?OutputKey=='RepositoryName'].OutputValue | [0]" --output text)
export AWS_SAGEMAKER_ROLE_ARN=$(aws cloudformation describe-stacks --stack-name iris-course \
  --query "Stacks[0].Outputs[?OutputKey=='ExecutionRoleArn'].OutputValue | [0]" --output text)
export AWS_MODEL_PACKAGE_GROUP=$(aws cloudformation describe-stacks --stack-name iris-course \
  --query "Stacks[0].Outputs[?OutputKey=='ModelPackageGroup'].OutputValue | [0]" --output text)
```

## Push the tested container

```bash
export AWS_ECR_HOST="${AWS_ECR_URI%%/*}"
aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin "$AWS_ECR_HOST"
docker tag iris-course:v1 "$AWS_ECR_URI:v1"
docker push "$AWS_ECR_URI:v1"
export AWS_IMAGE_DIGEST=$(aws ecr describe-images --repository-name "$AWS_ECR_REPOSITORY" \
  --image-ids imageTag=v1 --query 'imageDetails[0].imageDigest' --output text)
export AWS_IMAGE="$AWS_ECR_URI@$AWS_IMAGE_DIGEST"
cd python
uv sync --locked --extra aws
```

ECR tags are immutable in this template, so use `v2`, `v3`, etc. for changed
images. Both training and registry registration take the digest URI. The same
image bytes can be pushed to ACR and ECR, with registry-specific names. Review
[ECR repository settings](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-ecr-repository.html)
for scanning and tag behavior.

## Costs and storage retention

Create an AWS budget alert for the sandbox. Consult
[SageMaker AI pricing](https://aws.amazon.com/sagemaker/ai/pricing/),
[S3 pricing](https://aws.amazon.com/s3/pricing/) and
[ECR pricing](https://aws.amazon.com/ecr/pricing/) for the selected region.
Real-time endpoints continue charging when idle. A staging endpoint plus a
production endpoint uses two allocations, and an update may briefly add more.
Training jobs stop after completion or the configured 30-minute runtime limit;
that limit does not limit serving costs.

The stack deliberately **retains S3 and ECR on deletion** to avoid silently
destroying experiment evidence. Retained resources still cost money. Lesson 10
includes a cleanup helper that deletes explicitly named endpoints/configs/models,
registry versions and the stack, and can purge the dedicated retained resources
when requested. Versioned S3 buckets must have old versions and delete markers
removed as well as current objects. Save any evidence you need first.

**Done when:** you know the role ARN, bucket, package group and image digest,
and can distinguish your operator identity from SageMaker's execution role.

Next: [AWS lifecycle](10-aws-lifecycle.md).
