# Lesson 03: Evaluate, promote, and roll back

**Goal:** distinguish a trained model, a passing candidate, an approved release,
and the version actually serving requests. Start with lesson 02's two runs.

## Apply a small release policy

```bash
uv run iris evaluate baseline
uv run iris evaluate weak
```

The second command is expected to exit with status 1. Inspect each `gate.json`.
Our policy requires validation accuracy and macro F1 of at least 0.90. If a
production model exists, neither metric may fall more than 0.02 below its score
on the same validation data. Changed validation or test CSV hashes block the
comparison and require a separate benchmark review.

Macro F1 weights species equally. Accuracy can hide weak performance for a
minority class. This Iris split is balanced; on a real task, choose thresholds
from the cost of different errors and inspect class metrics, data slices, sample
sizes, and uncertainty. A 30-row validation set moves in 3.33-percentage-point
steps, so our 2-point regression allowance effectively forbids one extra error.
It is a teaching policy, not a universal threshold.

## Review and promote

Read the metrics, confusion matrix, data identity, and parameters first:

```bash
uv run iris promote baseline
uv run iris status
```

Promotion recomputes the gate against the **current** production model; an old
passing report cannot bypass a newer incumbent. It appends a decision to the
registry history and updates the pointer atomically. It does not restart a
running server or switch cloud traffic.

Try `uv run iris promote weak`. It must fail and leave the pointer on
`baseline`. Do not weaken the policy just to make a favorite model pass.

## Open the test set after selection

```bash
uv run iris test baseline
```

This saves `final-test.json` once and reports it on subsequent calls. With the
initial snapshot and default parameters, the current environment obtains 28/30
correct test predictions (93.3%). Treat this as a small-sample report. Do not
use successive test reports to select `C`. A poor final report calls for a
documented review and, if development resumes, a fresh independent benchmark;
cached reports cannot enforce honest experimental practice.

## Package the approved model

```bash
uv run iris export baseline --output releases/baseline
```

The directory contains the model, run metadata, monitoring baseline, gate and
checksum manifest. A sibling `releases/baseline.tar.gz` stores those files at the
archive root for SageMaker. The release excludes datasets. Exports refuse to
overwrite existing directories and require the current production version.
Treat exported directories as immutable.

## Practice rollback

```bash
uv run iris train --run-id candidate --C 10
uv run iris evaluate candidate
uv run iris promote candidate
uv run iris rollback baseline
uv run iris status
```

Rollback accepts only a previously promoted version and verifies its checksum.
The history preserves both decisions. In the next lesson, restart the local
service after changing its pointer. In cloud lessons, restore the prior
deployment or endpoint configuration. Keep the old runtime image and model files
available for the whole rollback window.

**Exercise:** explain why a 95% accurate model with the wrong feature ordering
or a broken HTTP response should still fail a release review.

**Done when:** the weak candidate is rejected, the history shows a promotion
and rollback, and you can distinguish approval from deployment.

Next: [serving and containers](04-serving-and-containers.md).
