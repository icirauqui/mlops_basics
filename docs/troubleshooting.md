# Troubleshooting the labs

Start with the exact command, working directory and version being used. Python
commands in the lessons run from `python/`; cloud setup commands run from the
repository root. Read the first useful exception and retain the run/job ID.

| Symptom | Likely cause and next check |
| --- | --- |
| `uv` cannot be found | Install uv and reopen the shell; see its official installation guide |
| A dependency is missing | Run `uv sync --locked`; add `--extra azure`, `--extra aws`, or `--all-extras` as appropriate |
| `import iris_mlops` fails in a notebook | Start Jupyter from `python/` and select that project's `.venv` kernel |
| Existing data/run/release directory error | Immutable paths are intentional; reuse the completed result or choose a new name |
| No production model | Run the evaluate and promote steps, or mount an exported release through MODEL_DIR |
| Model checksum mismatch | Restore the original trusted artifact or create a new run; do not edit checksum evidence to bypass the check |
| Promotion is rejected | Inspect gate.json; check absolute metrics, incumbent score and holdout hashes |
| Correct prediction but wrong version | The process loaded an earlier model; restart locally or inspect cloud traffic/config |
| HTTP 422 | Inspect the named feature contract, numeric limits, unknown fields and batch length |
| HTTP connection refused | Check service/container startup logs and the host port; only one server can bind a port |
| Drift report has null fields | Too few records or no matched labels; null accuracy does not mean zero accuracy |
| No records after a release | Check model-version filtering and the exported time window |
| Docker cannot build/pull | Check daemon availability, proxy/network access and `linux/amd64` platform support |
| Docker model not found | Mount a release containing release.json, not the original introductory model |
| Azure authorization fails | Check subscription/tenant, login expiry, data-plane roles and managed identities |
| Azure image pull fails | Verify ACR association, identity pull access and digest existence |
| Azure deployment unhealthy | Get deployment logs; check model mount, startup exceptions and port/routes |
| Azure diagnostic logs are empty | Enable endpoint diagnostic routing, allow ingestion delay, verify workspace ID and query scope |
| AWS access denied | Check SSO session, selected region/account, operator policy, execution role and iam:PassRole |
| AWS training cannot access input | Inspect bucket/prefix, execution-role policy and File channel paths |
| AWS endpoint fails health checks | Check CloudWatch startup logs, archive root, /ping route and port 8080 |
| AWS registry package rejected | Approval must be Approved, creation must be Completed, and release checksums must match |
| Resource quota error | Training and endpoint quotas differ; request supported CPU capacity or change instance type |
| AWS cleanup leaves storage | S3/ECR have Retain policies; use the dedicated purge step after preserving evidence |
| AWS stack deletion fails on package group | Delete the group's package versions and retry; verify referenced models are retired |

For partial cloud failures, inspect resources already created before retrying.
Deleting an endpoint does not delete every model, registry version, image, log,
alarm or object. Follow the full cleanup section even after a failed deployment.

For adapter changes, use the linked official SDK documentation in each cloud
lesson and run the contract tests. A local mock passing is not proof that a
provider accepted the configuration in your region. Keep account-specific
troubleshooting separate from changes to the model or its evaluation policy.

## After the folder reorganization

Run `uv sync --locked` from `python/` to install the `src/iris_mlops` package.
Use `uv run iris --help`; old commands such as `uv run workflow.py` no longer
refer to a file. The [command map](../python/README.md) lists replacements.
If a notebook cannot import `iris_mlops`, choose this project's `.venv` kernel
and restart it. Launch Jupyter with `uv run jupyter lab notebooks/`.

A notebook run does not create the terminal lab's named runs. If `baseline` is
missing, complete lesson 02's terminal commands. If an ID or export path already
exists, keep the previous evidence and choose a new one. Do not delete the registry
just to bypass a regression check. Relative `--bundle`, `--output` and file paths
are resolved from your current terminal directory.

Cloud commands need their extra on every `uv run` invocation, for example
`uv run --extra azure iris-azure status --endpoint "$AZURE_ENDPOINT"`. This keeps
uv from dropping optional dependencies during environment synchronization.
