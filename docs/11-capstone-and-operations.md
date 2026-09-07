# Lesson 11: Capstone and operational handover

**Goal:** demonstrate the complete model lifecycle and explain the operational
decisions without relying on notebook execution order or a remembered command.

## Capstone scenario

You own a small flower-classification API. A new batch of reviewed labels
arrives. A candidate must pass evaluation, be registered and staged, then replace
production. Shortly afterward an upstream measurement change causes a drift
alert. Decide whether to repair inputs, retrain, or roll back.

Use `examples/new-labels.csv` for the synthetic label-arrival exercise and
`uv run iris-simulate --shift 5` for the input incident. Do the local lifecycle first.
Repeat release and rollback in Azure and AWS when you have access, cleaning up
one cloud before starting the next.

## Evidence to hand over

| Deliverable | Completion criterion |
| --- | --- |
| Dataset contract and snapshot | Validated CSVs; no overlapping IDs; unchanged benchmark hashes |
| Experiment comparison | At least one accepted and one rejected candidate, with reasons |
| Model card | Owner, use, limitations, data/code/image identity, evaluation and review decision |
| Approved release | Immutable bundle and registry record tied to the same model bytes |
| Staging verification | Expected species and run ID; malformed input rejected |
| Release record | Exact local version, Azure deployment or AWS endpoint config serving |
| Monitoring record | Window, model version, service signals, input drift and label coverage |
| Incident note | Symptom, investigation, decision, remediation and verification |
| Rollback demonstration | Earlier approved version restored and smoke-tested |
| Cleanup record | No remaining endpoints; retained data/logs explicitly identified |

Grade each item as demonstrated, explained only, or missing. A learner has
completed a cloud lab only after performing its live endpoint checks; local SDK
tests and disabled notebook cells are not substitutes. Keep the local course
fully usable for learners without cloud accounts.

## A practical release runbook

1. Identify the production version actually serving and the matching incumbent
   in the evaluation registry. Resolve differences before evaluating a release.
2. Validate data ownership, schema and holdout isolation. Review any data changes.
3. Train with recorded code/dependency/image versions. Keep failed-run evidence.
4. Evaluate on validation data and review error slices, not only aggregate scores.
5. Approve/export the exact candidate. Record the reviewer and rollback target.
6. Stage using the immutable runtime image and release. Verify contract and version.
7. Switch production and observe error rate, latency and model behavior.
8. Roll back if needed; otherwise retire old compute after the rollback window.

Changing the local production pointer does not change existing cloud deployments.
Changing a cloud deployment does not update the local pointer. This course makes
those actions visible; a team registry and deployment controller should coordinate
them when several people or environments operate independently.

## Incident record template

```text
Time window and environment:
Serving model version / image digest:
Observed symptom and affected requests:
Service metrics (errors, latency, restarts):
Input/label evidence and sample counts:
Cause or remaining uncertainty:
Decision (repair data, roll back, retrain, observe):
Action taken and version after recovery:
Verification and follow-up owner:
```

Do not retrain on corrupted measurements just because monitoring found a shift.
Validate units and upstream changes first. During an incident, a restored
version is only useful if its artifact, dependencies and input contract still
work. Keep rollback artifacts until the operational risk has passed.

## What changes for a real production system

| Teaching simplification | Production extension and why |
| --- | --- |
| Tiny balanced Iris data | Representative data, temporal/entity splits, uncertainty, slice analysis and label governance |
| File registry, one operator | Durable registry with concurrency control, access policy and approval audit |
| Manual incumbent synchronization | Deployment metadata as a reliable source of the serving version |
| Checksum manifests | Trusted artifact store, signing/attestation and restricted promotion permissions |
| One CPU instance | Capacity/load testing, multiple instances, availability objectives and autoscaling |
| Full traffic/config switch | Canary or blue/green policy with measured thresholds and automatic rollback |
| All Iris payloads logged | Data minimization, sampling, retention, privacy review and protected logs |
| Mean-shift monitoring | Calibrated statistical/distribution tests, slices, label delay/coverage analysis |
| Operator-driven delivery | Reviewed CI/CD with workload identities, immutable build artifacts and environment gates |
| Explicit local retraining | Scheduled or event-driven reviewed data pipeline with lineage and failure recovery |
| Single real-time API | Batch jobs when latency needs permit; asynchronous processing when requests are long |

Feature stores, Kubernetes, distributed training, managed pipeline DAGs, MLflow,
and LLM evaluation may be useful next topics. Add them when a concrete scale,
team or reliability requirement calls for them; the basic release loop remains
the one you practiced here.

**Done when:** another learner can follow your evidence to reproduce the model,
identify what is serving, investigate a problem, recover, and remove lab costs.
