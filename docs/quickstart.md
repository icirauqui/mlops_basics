# Your first local release in about 20 minutes

This is a short preview of the complete lifecycle. You need a terminal and
[uv](https://docs.astral.sh/uv/getting-started/installation/); no Docker or cloud
account yet. Windows users should use WSL2 for these Bash commands.

## 1. Set up and make a dataset

From the repository root:

```bash
cd python
uv sync --locked
uv run iris-data prepare
uv run iris-data validate
```

Expected: 90 training, 30 validation and 30 test rows. If `data/iris` already
exists, skip `prepare` and run `validate`. Training learns from the training
rows; release selection uses validation; the test rows stay closed for now.

## 2. Train, evaluate and approve

```bash
RUN=$(uv run iris train)
echo "$RUN"
uv run iris evaluate "$RUN"
```

Inspect the report: `passed` should be `true` for the default Iris candidate.
Accuracy and macro F1 must reach 0.90, with no excessive regression against the
current approved model. If the gate fails, inspect the report before continuing.
Approval is a separate decision:

```bash
uv run iris promote "$RUN"
uv run iris export "$RUN" --output "releases/$RUN"
uv run iris status
```

Expected: `production` contains your run ID. The files under `releases/` are the
reviewed model bundle. Promotion changes a local pointer; it does not start an API.
Auto-generated IDs make this preview repeatable without overwriting old runs.

## 3. Serve and ask for a prediction

In the same terminal:

```bash
uv run uvicorn iris_mlops.serve:app --host 127.0.0.1 --port 8080
```

Leave it running. In a **second terminal**, change to this repository's `python/`
folder and run:

```bash
curl -fsS http://127.0.0.1:8080/health
curl -fsS http://127.0.0.1:8080/predict \
  -H 'Content-Type: application/json' --data @examples/sample-request.json
```

Expected: prediction `setosa` and `model_version` equal to the run ID from step 2.
Open `http://127.0.0.1:8080/docs` to try the API interactively. Stop the server with
Ctrl-C in the first terminal.

## 4. Explore, then follow the lessons

```bash
uv run jupyter lab notebooks/02-local-lifecycle.ipynb
```

Run cells from the top. The notebook creates its own temporary registry, so you
can safely explore rejection and rollback. Select the project `.venv` kernel if
your editor asks. Notebook state and terminal lab state are separate.

Continue with [lesson 01](01-iris-training.md) if training is new to you, or
[lesson 02](02-data-and-experiments.md) to understand the evidence behind each
release. The preview uses generated run IDs, so lesson 02's named `baseline`
and `weak` runs remain available. See the [course guide](00-course-guide.md) for
the full local → Azure → AWS route, and [troubleshooting](troubleshooting.md)
if an expected result differs.
