# Python labs

Start with the [20-minute local walkthrough](../docs/quickstart.md), then follow
[lessons 01–11](../docs/00-course-guide.md). Run terminal commands from `python/`
unless a lesson explicitly says repository root.

```bash
uv sync --locked
uv run jupyter lab notebooks/
```

`uv` creates `.venv`, installs the locked dependencies and installs `iris_mlops`
from `src/` in editable mode. Edits to the scripts are available on the next run;
restart a notebook kernel after changing imported code. No `sys.path` edits or
manual environment activation are needed. Use the project `.venv` as your kernel.

## Folder map

```text
python/
  src/iris_mlops/    # reusable Python scripts, installed as a package
  notebooks/        # exploration and guided controls; imports the package
  tests/            # lifecycle and cloud contract checks
  tools/            # notebook and Docker verification scripts
  examples/         # sample API request and reviewed synthetic labels
  pyproject.toml    # dependencies and command entry points
  uv.lock          # exact resolved dependency versions
  Dockerfile       # shared cloud training/serving image
  data/            # generated dataset snapshots
  state/           # generated runs, local registry, logs and receipts
  releases/        # generated approved model bundles
  downloads/       # generated managed training outputs
  artifacts/       # generated introductory model only
```

Generated folders appear when their lab runs. They are ignored by Git.

## Commands and source files

| Command after `uv run` | Source in `src/iris_mlops/` | Purpose |
| --- | --- | --- |
| `python -m iris_mlops.train` / `python -m iris_mlops.predict` | `train.py`, `predict.py` | Introductory 80/20 example |
| `iris-data` | `data.py` | Prepare and validate the lifecycle dataset |
| `iris` | `workflow.py` | Train, evaluate, promote, test, export, import, status, rollback |
| `uvicorn iris_mlops.serve:app` | `serve.py` | Versioned prediction API |
| `iris-simulate` / `iris-monitor` / `iris-logs` | `simulate.py`, `monitor.py`, `normalize_logs.py` | Traffic, reports and cloud log conversion |
| `iris-retrain` | `retrain.py` | Train from reviewed additional labels |
| `--extra azure iris-azure` | `azure_cloud.py` | Managed Azure ML lifecycle |
| `--extra aws iris-aws` / `--extra aws iris-cleanup-aws` | `aws_cloud.py`, `aws_cleanup.py` | SageMaker lifecycle and cleanup |

Use `uv run iris --help` or `uv run iris train --help` to explore options.
Single IDs, paths and ARNs print as plain text, so they can be captured with
`RUN=$(uv run iris train)`. Reports print JSON. A failed evaluation exits with
status 1; that is expected in the weak-model exercise.

## Notebooks

Run cells from top to bottom. `iris.ipynb` introduces training;
`02-local-lifecycle.ipynb` compares candidates and practices release decisions;
`03-monitoring-retraining.ipynb` investigates drift and labels;
`04-azure.ipynb` and `05-aws.ipynb` guide cloud operations.

Lifecycle notebooks use temporary registries; they do not create the command-line
lab's `baseline` run. Cloud actions require `RUN_CLOUD=True`, real names and
credentials. Read the corresponding setup lesson first. The automated verifier
always skips cells tagged `cloud` even if that switch is edited.

## Verification and path conventions

```bash
uv sync --locked --all-extras
uv run --all-extras pytest -q
uv run tools/verify_notebooks.py
# After the Docker build in lesson 04:
uv run tools/verify_container.py --image iris-course:v1
```

Use `--extra azure` or `--extra aws` for provider commands. Local lessons need
neither SDK. Notebook/test tools belong to the default `dev` dependency group;
the image installs only runtime dependencies.

Default data/state paths resolve to this project even from `notebooks/`. Explicit
relative CLI paths resolve from your terminal's current directory. Outside an
editable checkout (for example a regular wheel installation), set `IRIS_WORKSPACE`
to a writable workspace before starting Python; the Dockerfile sets it to `/app`.
Executed notebook copies go in `notebooks/executed/` and are ignored by Git.
