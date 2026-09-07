# Lesson 08: Train, release, and operate on Azure

**Goal:** perform the same lifecycle using Azure ML managed services. Keep lesson
07's variables set. All Python commands run from `python/` with `--extra azure`.

## 1. Submit a managed training job

```bash
uv run --extra azure iris-azure train --image "$AZURE_IMAGE"
```

The adapter validates the local snapshot, registers a hash-versioned data asset,
and submits an Azure ML command job on `cpu-cluster`. The job runs the shared
`iris_mlops.cloud_train` module from the image and saves a candidate run as a named output.
The CLI prints the job name and streams logs; first-time compute provisioning
can take much longer than training. In Azure ML Studio, inspect the job's inputs,
environment, output files, validation report and logs. See the
[command-job schema](https://learn.microsoft.com/en-us/azure/machine-learning/reference-yaml-job-command?view=azureml-api-2)
and [data inputs/outputs](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-read-write-data-v2?view=azureml-api-2).

Copy the actual job name, then download:

```bash
export AZURE_JOB='job-name-printed-by-training'
uv run --extra azure iris-azure download "$AZURE_JOB" --output downloads/azure
```

The download command prints directories containing `run.json`; use the one for
this job. Training outputs include the tiny Iris snapshots for auditability.
Production release exports omit them; real datasets should remain in governed
storage with references recorded as lineage.

## 2. Import, review and register the exact release

```bash
export AZURE_RUN_PATH='downloads/azure/actual-directory-containing-run-json'
AZURE_RUN=$(uv run iris import "$AZURE_RUN_PATH")
export AZURE_RUN_V1="$AZURE_RUN"
uv run iris evaluate "$AZURE_RUN"
uv run iris promote "$AZURE_RUN"
uv run iris export "$AZURE_RUN" --output "releases/$AZURE_RUN"
uv run --extra azure iris-azure register --bundle "releases/$AZURE_RUN" \
  --version 1 --image "$AZURE_IMAGE"
```

Replace the download path with the actual printed directory; SDK output layouts
can differ. Import never promotes. Use the same local registry throughout these
lessons so the candidate is compared against the retained incumbent. For a real
release, ensure that incumbent matches the model currently serving in the target
environment; this single-operator course does not synchronize independent
cloud operators' decisions automatically.

Azure model version `1` now holds a reviewed bundle with approval, run ID,
checksum and runtime-image tags. Tags express this course's review convention;
they are not a native protected approval workflow. Limit who can modify/register
models and who can deploy. Use a new version number for every release.

## 3. Create an endpoint and stage a deployment

Choose an endpoint name unique in the region:

```bash
export AZURE_ENDPOINT='your-unique-iris-endpoint'
uv run --extra azure iris-azure create-endpoint --endpoint "$AZURE_ENDPOINT"
uv run --extra azure iris-azure deploy --endpoint "$AZURE_ENDPOINT" \
  --deployment blue --version 1
uv run --extra azure iris-azure smoke --endpoint "$AZURE_ENDPOINT" --deployment blue
uv run --extra azure iris-azure status --endpoint "$AZURE_ENDPOINT"
```

Repeating `create-endpoint` preserves an existing course endpoint and its traffic.
If setup or deployment fails, inspect status/logs before trying a new name.

The custom container uses the registered model mount and explicit health/scoring
routes. `deploy` does not set traffic. Direct invocation of `blue` lets you
test the candidate before production routing changes. The endpoint uses Entra
authentication (`aad_token`), with credentials obtained through the SDK.
See [custom container deployment](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-deploy-custom-container?view=azureml-api-2).

```bash
uv run --extra azure iris-azure switch --endpoint "$AZURE_ENDPOINT" --deployment blue
uv run --extra azure iris-azure smoke --endpoint "$AZURE_ENDPOINT"
```

Switching rechecks the target, saves previous traffic locally under `state/`,
and sends 100% to `blue`. Inspect the served version and status, then record the
deployment in your model card. A successful endpoint creation is not enough.

## 4. Ship a second version and roll back

For the second release, reuse the tested image and train a local candidate with
`C=10`; step 1 already demonstrated managed training. Use a fresh run and model
version if repeating the exercise. Inspect the gate before promotion:

```bash
AZURE_RUN_V2=$(uv run iris train --C 10)
uv run iris evaluate "$AZURE_RUN_V2"
uv run iris promote "$AZURE_RUN_V2"
uv run iris export "$AZURE_RUN_V2" --output "releases/$AZURE_RUN_V2"
uv run --extra azure iris-azure register --bundle "releases/$AZURE_RUN_V2" \
  --version 2 --image "$AZURE_IMAGE"
```

Always use a new deployment name for a new release; do not replace a live
deployment in place. Now stage, switch, and restore v1:

```bash
uv run --extra azure iris-azure deploy --endpoint "$AZURE_ENDPOINT" \
  --deployment green --version 2
uv run --extra azure iris-azure smoke --endpoint "$AZURE_ENDPOINT" --deployment green
uv run --extra azure iris-azure switch --endpoint "$AZURE_ENDPOINT" --deployment green
uv run --extra azure iris-azure switch --endpoint "$AZURE_ENDPOINT" --deployment blue
```

The last command is rollback. It also smoke-checks the old version. Verify
production, then restore the local approval pointer to match that environment:

```bash
uv run --extra azure iris-azure smoke --endpoint "$AZURE_ENDPOINT"
uv run iris rollback "$AZURE_RUN_V1"
```

Keep `blue`
available during the rollout window; delete it afterward if no longer needed.
Both active deployments incur compute charges even if one receives zero traffic.
Weighted canaries are an extension: this course uses a visible staged check and
a full switch to keep the first release procedure small.

## 5. Monitor service and model behavior

```bash
uv run --extra azure iris-azure logs --endpoint "$AZURE_ENDPOINT" --deployment blue
```

For retained logs, open the endpoint resource in Azure Portal → Diagnostic
settings. Send `AmlOnlineEndpointConsoleLog`, `AmlOnlineEndpointTrafficLog`, and
`AmlOnlineEndpointEventLog` to a Log Analytics workspace in the course group.
Choose a short retention period suitable for the lab. New diagnostic routing
can take time before records appear. This custom server logs to stdout; creating
an Application Insights resource does not automatically instrument it.

Run the repository file `cloud/azure/monitoring.kql` queries in Log Analytics. In Azure Monitor,
chart request count, latency and failures, then create an alert with a five-minute
window and an action group you control. A useful lab target is at least one 5xx
in five minutes; for real traffic use an error-rate objective and minimum volume.
Create a latency alert only after measuring normal platform latency. The exact
metric names and dimensions are available from the endpoint's Metrics screen.
See [Azure endpoint monitoring](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-monitor-online-endpoints?view=azureml-api-2).

Export recent console messages for the same Python monitoring report:

```bash
export AZURE_LOG_WORKSPACE_ID='log-analytics-workspace-customer-id'
az monitor log-analytics query --workspace "$AZURE_LOG_WORKSPACE_ID" \
  --analytics-query "AmlOnlineEndpointConsoleLog | where TimeGenerated > ago(1h) | where _ResourceId endswith '/onlineEndpoints/$AZURE_ENDPOINT' | project Message" \
  --query '[].Message' -o json > state/azure-messages.json
uv run iris-logs state/azure-messages.json state/azure-predictions.jsonl
uv run iris-monitor --bundle "releases/$AZURE_RUN_V1" --log state/azure-predictions.jsonl
```

Use the Log Analytics **workspace/customer ID**, not its Azure resource ID. Add
`--feedback` once you have independent labels. A handful of smoke calls yields
insufficient drift data by design. For scheduled monitoring, run this export and
report on an agreed window and deliver findings to an owner before retraining.

## 6. Clean up

```bash
uv run --extra azure iris-azure delete-endpoint --endpoint "$AZURE_ENDPOINT"
az group delete --name "$AZURE_RESOURCE_GROUP"
```

Confirm the dedicated group only contains course resources. Group deletion also
removes cluster, workspace dependencies, registry, and diagnostic resources in
that group. If you used a shared Log Analytics workspace, remove the lab's
diagnostic settings/alerts and account for retained logs separately.

**Done when:** you have a remote training job, an approved version, a successful
staged smoke check, a traffic switch and rollback, a monitoring query, and
verified resource cleanup. Record any live cloud failures in the model card.

Next: [AWS setup](09-aws-setup.md).
