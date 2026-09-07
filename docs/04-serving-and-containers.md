# Lesson 04: Serve the model with a stable contract

**Goal:** run one versioned prediction service locally and in a container.
Complete lesson 03 and keep `baseline` as your production version.

## Start the API

From `python/`:

```bash
PREDICTION_LOG=state/predictions.jsonl \
  uv run uvicorn iris_mlops.serve:app --host 127.0.0.1 --port 8080
```

In a second terminal in the same folder:

```bash
curl -fsS http://127.0.0.1:8080/health
curl -fsS http://127.0.0.1:8080/predict \
  -H 'Content-Type: application/json' --data @examples/sample-request.json
```

Visit `http://127.0.0.1:8080/docs` for the interactive schema. The request contains
`instances`, a list of 1–100 objects with four named centimeter measurements.
The response contains a request ID, model version, species predictions, class
ordering, and probabilities. Probabilities follow the returned `classes` order;
they are not independently validated confidence bounds.

`/ping` and `/invocations` are aliases for cloud hosting. Incorrect, missing,
nonfinite, negative, oversized, or unknown feature fields yield HTTP 422.
Check the model version, not just HTTP 200. The service loads once at startup,
so local promotion requires restarting the process. Use Ctrl-C to stop.

## Build and run the container

From `python/`, after exporting the release in lesson 03:

```bash
docker build --platform linux/amd64 -t iris-course:v1 .
docker run --rm --name iris-course \
  -p 127.0.0.1:8080:8080 \
  -v "$PWD/releases/baseline:/models:ro" \
  -e MODEL_DIR=/models iris-course:v1
```

Repeat the health and prediction calls. The model is mounted separately from
the runtime image: a model-only release can reuse a tested image. The Dockerfile pins base images by digest. Update those pins deliberately and
rerun the checks when taking runtime updates. The image
contains the lockfile, training code and inference code, with notebook and cloud
SDK dependencies omitted. `linux/amd64` matches the cloud lesson CPU instances,
including when building on Apple Silicon.

Stop it with `docker stop iris-course`. To retain JSONL logs across restarts,
also mount a writable logs directory and set `PREDICTION_LOG=/logs/predictions.jsonl`.
Cloud lessons use stdout logs; container filesystems are not durable storage.

For an automated end-to-end check, run `uv run tools/verify_container.py --image iris-course:v1`.
It trains a disposable model inside the image, imports/approves it locally, then
checks both cloud mount layouts and valid/invalid HTTP requests. It stops its
containers and removes temporary run files afterward. Docker must share access
to the repository directory with the Python process.

The entry point understands SageMaker's `train` and `serve` commands. Training
writes its candidate to `/opt/ml/model`; hosting reads the extracted release
there. Our Azure adapter mounts the release at `/models` and sets `MODEL_DIR`;
the server also supports `AZUREML_MODEL_DIR` for other Azure configurations.
Both use port 8080 and the same JSON contract. See the
[SageMaker training contract](https://docs.aws.amazon.com/sagemaker/latest/dg/your-algorithms-training-algo-dockerfile.html),
[hosting contract](https://docs.aws.amazon.com/sagemaker/latest/dg/your-algorithms-inference-code.html),
and [Azure custom containers](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-deploy-custom-container?view=azureml-api-2).

## What a smoke check proves

A known setosa example should return `setosa` and the expected version. This
checks artifact loading, schema, preprocessing and inference together. It does
not estimate generalization, throughput, or availability. Test invalid requests
too. Cloud commands repeat this check before switching production.

The local API has no authentication and binds to loopback. Cloud endpoints add
platform authentication. The single-process image runs as root for compatibility
with managed training; harden the serving image and scan its dependencies and base images
before using this pattern for real users. Only deserialize trusted joblib files.

**Done when:** the direct process and Docker return the same model version and
prediction, and a malformed request returns 422. Shut down both when finished.

Next: [monitoring and retraining](05-monitoring-and-retraining.md).
