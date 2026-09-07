# Lesson 06: Continuous integration and release delivery

**Goal:** automate repeatable checks while keeping release decisions visible.

## Run the checks locally

From `python/`:

```bash
uv sync --locked --all-extras
uv run --all-extras pytest -q
uv run tools/verify_notebooks.py
```

Tests cover split isolation, training-only scaling, failed promotion, benchmark
changes, rollback, artifact checksums, API validation, delayed labels, drift,
retraining and downloaded training runs. Cloud tests validate selected SDK
contracts without credentials; they cannot prove IAM or quota works.

Notebook verification executes each notebook with a fresh kernel and writes
executed copies to `notebooks/executed/`. Cells tagged `cloud` are skipped, so the
verification command never provisions or calls cloud endpoints. Teaching
notebooks also default cloud execution to disabled when opened interactively.

## CI in this repository

`.github/workflows/course-ci.yml` runs on pushes and pull requests. It installs
locked dependencies, runs tests, executes notebooks, builds the container, and
smoke-tests a disposable model through HTTP. The registry used for this check
is temporary CI state; passing this fixture does not approve a production model.

The workflow has read-only repository permissions and no cloud credentials.
Actions are pinned to full commit IDs, and checkout does not persist credentials.
The [setup-uv action](https://github.com/astral-sh/setup-uv) provides the same uv
version as the Docker build. In a GitHub repository, make this job a required
check in branch protection and require code review before merging changes.

## Delivery is a sequence, not another training run

| Step | How this course performs it |
| --- | --- |
| Check code and contracts | Automated CI |
| Train and record candidate | Local script or managed cloud job |
| Evaluate against incumbent | `iris evaluate`, using the retained registry |
| Review model evidence | Student/operator examines the gate and model card |
| Approve and export | Explicit `promote` and `export` commands |
| Register and stage | Provider-specific scripts |
| Validate and release | Smoke check followed by explicit traffic/config switch |
| Watch and recover | Monitoring report, platform metrics, explicit rollback |

Keep the same approved model bytes between staging and production. Do not
retrain while deploying or independently rebuild a mutable image tag in each
environment. Cloud scripts require image digests. Record the release run ID,
image digest, native registry version, endpoint/deployment/configuration, review
decision and rollback target together.

Lessons 08 and 10 provide the actual delivery commands. They are deliberately
operator-driven continuous delivery rather than automatic production deployment
on every push. This keeps credentials, billable actions and approvals simple.

## Extending to a team pipeline

When moving beyond the lesson, store evaluation evidence and a production
registry durably rather than recreating an empty registry on each CI runner.
Before a release, synchronize the incumbent used by the gate with the model
actually serving. Use cloud workload identity/OIDC for CI credentials and a
protected deployment environment with reviewers; never save access keys in the
repository. Re-run the gate if production changes between review and release.

Use a manual dispatch or approved pipeline stage to consume an immutable release
artifact from a successful build. Limit cloud write permissions to that stage.
For automatic retraining, trigger on reviewed data arrival or a scheduled data
review; a drift alert alone should not silently retrain and deploy a model.

**Exercise:** introduce an unknown request field in a test request. Verify CI
catches any change that accidentally stops rejecting it. Explain why a successful
cloud smoke check does not replace the validation gate.

**Done when:** tests and notebooks pass locally, and you can describe exactly
where human review, cloud credentials and rollback enter the delivery sequence.

Next: [Azure setup](07-azure-setup.md).
