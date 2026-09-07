# Course review: 7 September 2026

The review covered the learner path, Python layout, command examples, release
logic, CI, cloud templates, container contracts, authentication and monitoring.
The course retains one small classifier and one shared runtime. Advanced team
infrastructure remains clearly identified as an extension.

## Changes made for clarity and correctness

- Added a short local walkthrough, stage checkpoints and glossary.
- Moved reusable code into `python/src/iris_mlops/`, notebooks into
  `python/notebooks/`, and verification utilities into `python/tools/`.
- Installed the package through uv; introduced short commands and stable default
  workspace paths so notebooks can import code without modifying `sys.path`.
- Updated documentation, notebook imports, Docker and CI for the new layout.
- Made single IDs/ARNs printable as plain text for shell variable capture.
- Added explicit second-release instructions and aligned local approval pointers
  with the cloud version after the rollback drill.
- Preserved Azure endpoint traffic when repeating endpoint setup; rejected names
  with different ownership/authentication and propagated access failures.
- Rejected mutable training image tags before uploading data or creating assets.
  AWS hosting also requires the approved package to have completed creation.
- Pinned container bases by digest and CI actions by commit. Retained a tested
  dependency lockfile; upgrading every package independently is not a release policy.

## Official documentation checked

These are the primary references for the implementation choices, checked on the
review date. Portal labels, available instance sizes, quota and prices can change.

| Topic | Course decision and official reference |
| --- | --- |
| Python package layout | A uv project with a build backend and `src` package; [uv project initialization](https://docs.astral.sh/uv/concepts/projects/init/) and [project layout](https://docs.astral.sh/uv/concepts/projects/layout/) |
| Azure API generation | Uses `azure-ai-ml` SDK v2 command jobs and the `ml` CLI extension. SDK v1 support ended on 30 June 2026; [Azure migration guidance](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-migrate-from-v1?view=azureml-api-2) |
| Azure service choice | Custom tabular model training/hosting uses Azure ML; [Microsoft service selection](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/data-science-and-machine-learning). Foundry resources are not prerequisites for this course |
| Azure hosting | Custom image, model mount, explicit liveness/readiness/scoring routes; [custom-container deployment](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-deploy-custom-container?view=azureml-api-2) |
| Azure authentication | Managed endpoints use Entra `aad_token`, with operator permissions for invocation; [endpoint authentication](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-authenticate-online-endpoint?view=azureml-api-2) |
| Azure monitoring | Diagnostic console, traffic and event logs go to Log Analytics; custom stdout does not automatically instrument Application Insights; [online endpoint monitoring](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-monitor-online-endpoints?view=azureml-api-2) |
| AWS service/API | Uses SageMaker AI and boto3 service APIs; [managed training request](https://docs.aws.amazon.com/boto3/latest/reference/services/sagemaker/client/create_training_job.html). A separate high-level SageMaker SDK is not needed for these calls |
| AWS container contract | `train`/`serve`, `/opt/ml` locations, port 8080 and `/ping`/`/invocations`; [training containers](https://docs.aws.amazon.com/sagemaker/latest/dg/your-algorithms-training-algo-dockerfile.html) and [inference containers](https://docs.aws.amazon.com/sagemaker/latest/dg/your-algorithms-inference-code.html) |
| AWS image identity | Digest image URIs in model packages; [container definition API](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_ModelPackageContainerDefinition.html) |
| AWS approval | Pending review followed by explicit approval; [model package approval](https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry-approve.html) |
| AWS rollout | Staging smoke check and explicit production update/rollback; automatic rollback requires additional configuration and alarms; [deployment guardrails](https://docs.aws.amazon.com/sagemaker/latest/dg/deployment-guardrails.html), [all-at-once configuration](https://docs.aws.amazon.com/sagemaker/latest/dg/deployment-guardrails-blue-green-all-at-once.html), [exclusions](https://docs.aws.amazon.com/sagemaker/latest/dg/deployment-guardrails-exclusions.html) |
| CI actions | Reviewed [checkout releases](https://github.com/actions/checkout/releases/tag/v7.0.1) and [setup-uv](https://github.com/astral-sh/setup-uv); workflow pins their exact commits |

## Teaching scope and validation limits

The first three lessons should be approachable with basic Python. Cloud labs are
intermediate operations work: account permissions, managed identities, quotas,
resource names and billing still require attention. Completing the local loop
first makes the same release steps recognizable on each provider.

The course includes a complete small release lifecycle. It does not claim that
30 validation examples, one endpoint instance, approval tags or a local JSON
registry are sufficient for an enterprise production service. The model card,
monitoring lesson and capstone explain these boundaries and the next extensions.
A passed validation gate is evidence for review; it is not permission to ignore
model behavior, security, service reliability or label quality.

The reorganized project passed these local checks:

| Check | Result |
| --- | --- |
| Lifecycle and cloud contract tests | 16 passed |
| Notebook execution | All 5 notebooks' local cells passed; cloud-tagged cells skipped |
| uv distribution build | Source distribution and wheel built successfully |
| Shared Docker runtime | Built successfully with pinned bases and regular wheel installation |
| Docker lifecycle check | Training, approval/export, Azure and SageMaker mounts, versioned inference and invalid-request rejection passed |
| CloudFormation / Bash setup | `cfn-lint` and `bash -n` passed |
| Source lint and documentation | Ruff checks and local Markdown/notebook links passed |

Tests emit upstream deprecation warnings from Starlette and the Azure SDK's
Marshmallow integration. These did not fail the checks; revisit them when
upgrading dependencies. Notebook kernels also emit a local transport warning.

Cloud contract tests use mocks and SDK schemas. They do not authenticate or allocate
resources in an Azure subscription or AWS account. Live training, image pulls,
endpoint updates, alerts and resource cleanup must be verified during the labs.
The GitHub Actions workflow must also run in the learner's repository to verify
the hosted runner environment. No cloud deployment was executed during this review.

## Keep the course current

Before teaching a new cohort, revisit the linked service contracts and confirm
quota in the selected regions. Review dependency updates with `uv lock --upgrade`,
then `uv sync --locked --all-extras`; inspect the lockfile diff and run the lesson
checks. Update Docker base digests and action pins deliberately. Build and test
the new image, push a new image tag and record its digest. Retain old approved
artifacts and image digests for rollback. Never replace a deployed release's
runtime merely because a newer dependency exists.
