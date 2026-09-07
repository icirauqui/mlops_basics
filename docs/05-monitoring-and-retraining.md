# Lesson 05: Monitor, investigate, and retrain

**Goal:** notice problems, distinguish causes, and produce a reviewed candidate
from new labels. Start the API from lesson 04 with prediction logging.

## Generate observable traffic

From another terminal in `python/`:

```bash
uv run iris-simulate
uv run iris-monitor --bundle releases/baseline --log state/predictions.jsonl \
  --feedback state/feedback.jsonl
uv run iris-simulate --shift 5
uv run iris-monitor --bundle releases/baseline --log state/predictions.jsonl \
  --feedback state/feedback.jsonl --output state/drift-report.json
```

The simulator replays training examples, then artificially increases petal
length. These are synthetic teaching events, not independent production
evaluation. The shifted inputs retain their original labels to illustrate a
sensor or schema problem. Do not automatically add them to training data.

Feedback uses `request_id`, zero-based `row_index`, and `label`. This joins later
ground truth to the prediction that actually happened, including batched
requests. Never use the model's prediction as the supposedly true label.

## Read the report

| Signal | Interpretation | First response |
| --- | --- | --- |
| HTTP errors, platform latency, restarts | Service health | Check deployment, saturation and request schema |
| Input means move from training baseline | Possible input drift | Inspect units, upstream releases, population changes |
| Accuracy drops on labeled observations | Possible performance degradation | Check labels, lag, coverage, slices and concept changes |

The script filters to the release's model version. It reports request/sample
counts, p95 prediction latency, feature mean shifts in training-standard-deviation
units, and accuracy only when labels exist. It requires at least 30 samples
before flagging drift, and 30 matched labels before an accuracy alert. The
illustrative thresholds are mean shift above 1 standard deviation and accuracy
below 90%.

Mean shift is not a statistical significance test and can miss changes in
variance, tails or relationships between features. Drift is not proof of
accuracy loss. Delayed or selectively observed labels can bias accuracy. Choose
real windows and thresholds from expected traffic, alert costs and variability.

Prediction latency excludes network transport and some request processing.
Use platform latency and errors for service objectives. The script analyzes its
whole input file. Scheduled jobs should export a defined recent window, keep
versions separate, and record window boundaries with the report.

## Retrain from reviewed labels

Inspect `examples/new-labels.csv`: six **synthetic** observations with human-set
labels for this exercise, using the existing schema.

```bash
uv run iris-retrain --new-labels examples/new-labels.csv --output-data data/iris-v2
```

The script appends these rows to training data, copies validation/test unchanged,
validates isolation, trains a run and prints its gate. It never promotes
automatically. Use the printed ID to evaluate, review, promote and export with
`uv run iris`. Repeated exercises need a fresh output directory; avoid appending
the same IDs twice.

In production, review label source and ownership, keep true labels separate from
predictions, and exclude benchmark observations. Preserving CSV bytes supports
comparisons but cannot stop someone assigning a held-out flower a new ID.

`notebooks/03-monitoring-retraining.ipynb` reproduces the loop with a temporary registry
and no separate web server, contrasting unlabeled drift with labeled accuracy.

## Incident drill

1. Record the alert, time window and model version.
2. Inspect request schema, feature distributions, platform logs and labels.
3. If the release caused the problem, roll back and verify the served version.
4. If upstream data is wrong, fix that input path before retraining.
5. If reviewed data supports an update, train and gate a new candidate.
6. Stage, smoke-check, switch, and watch the same monitoring window.

For a scheduled local check, have cron or your scheduler call the monitoring
command with the full path to `.venv/bin/python`, working directory, recent
logs and versioned release. Decide who owns alerts before adding notifications.
Cloud monitoring and alert creation appear in lessons 08 and 10.

**Done when:** you can trigger drift, explain why absent labels mean unknown
accuracy, and produce a candidate with unchanged validation/test hashes.

Next: [CI and release delivery](06-ci-and-delivery.md).
