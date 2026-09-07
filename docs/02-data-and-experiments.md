# Lesson 02: Data contracts and experiment records

**Goal:** reproduce a candidate and explain exactly what it learned from.
Complete lesson 01 first. Run the commands below from `python/`.

## Make a versioned dataset

```bash
uv run iris-data prepare
uv run iris-data validate
```

The first command creates `data/iris/{train,validation,test}.csv`: 90 training,
30 validation, and 30 test rows. A fixed seed and stratification preserve 30/10/10
examples of each species. It refuses to overwrite the directory. If it already
exists, validate it and continue; use `--directory data/another-snapshot` for a
separate exercise.

| Column | Meaning and contract |
| --- | --- |
| `sample_id` | Stable observation identifier, unique across all three splits |
| `sepal_length`, `sepal_width` | Sepal measurements, centimeters |
| `petal_length`, `petal_width` | Petal measurements, centimeters |
| `label` | `setosa`, `versicolor`, or `virginica` |

All features must be present, finite, positive and at most 30 cm; unknown
columns and labels fail validation. The broad upper bound catches basic input
mistakes, not botanical implausibility. These checks are applied before training
and the feature contract is also enforced at the API boundary.

Stable IDs prevent overlap of identified observations. They do not detect the
same real flower assigned two different IDs. On real data, establish identity,
deduplicate upstream, and split by entity or time where appropriate. Do not
randomly split records from the same patient, device, or future period across
evaluation and training.

## Train two candidates

```bash
uv run iris train --run-id baseline --C 1
uv run iris train --run-id weak --C 0.000001
```

Run IDs are unique and never overwritten. Omit `--run-id` to generate one.
Training uses only `train.csv`; the scaler is fitted inside the pipeline. The
initial metric report evaluates `validation.csv`. No test score is calculated
yet. Look inside `state/runs/baseline/`:

| File | Evidence |
| --- | --- |
| `data/*.csv` | Exact snapshot used by this run |
| `run.json` | Parameters, timestamp, Python/scikit-learn versions, source/lockfile hashes, Git commit if available, data/model checksums |
| `model.joblib` | Fitted scaler and classifier together |
| `metrics.json` | Validation accuracy, macro F1 and confusion matrix |
| `baseline.json` | Training feature means and standard deviations for monitoring |

Source hashes identify actual Python files even with uncommitted edits. They do
not archive the source: commit your work and keep the matching lockfile or
container digest. Bit-for-bit model bytes can still vary across platforms;
fixed splits and dependencies improve reproducibility without guaranteeing
identical floating-point behavior on every machine.

## Explore interactively

```bash
uv run jupyter lab notebooks/02-local-lifecycle.ipynb
```

The notebook uses a temporary dataset and registry. It shows a run comparison
table without altering `state/registry.json`. For a larger course, these file
records can later be replaced by MLflow; the concepts are the same. MLflow, DVC,
and feature stores are not additional prerequisites here.

**Exercise:** copy the dataset, remove one feature value, and run validation.
Restore it, then put a training sample ID in the validation file. Explain both
errors before moving on.

**Done when:** you can locate a run's data hash and parameters, identify the
source of its metrics, and explain why preprocessing and candidate selection
must not learn from the test split.

Next: [evaluation and promotion](03-evaluation-and-promotion.md).
