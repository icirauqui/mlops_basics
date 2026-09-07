# Model card: Iris course baseline

This describes the default lesson 02 baseline. Copy it for each reviewed release
and fill in identifiers from your actual run; do not treat example metrics as
evidence for a different model.

| Field | Baseline description / value to record |
| --- | --- |
| Purpose | Teach the MLOps lifecycle for a small multiclass classifier |
| Intended users | Course learners operating local or sandbox cloud environments |
| Owner and reviewer | Fill in for your exercise |
| Model | StandardScaler followed by LogisticRegression, C=1, max_iter=200 |
| Inputs | Four named positive centimeter measurements; see the API schema |
| Outputs | Species, probabilities in returned class order, request ID and run ID |
| Data | scikit-learn Iris, fixed stratified 90/30/30 train/validation/test split |
| Data/code/dependencies | Copy hashes and versions from run.json; retain uv.lock |
| Runtime image | Record the immutable registry URI with digest |
| Validation | Initial baseline: accuracy 0.9333, macro F1 0.9333 on 30 examples |
| Final test | Initial selected baseline: accuracy 0.9333 on 30 examples; run the explicit test-report command |
| Release policy | Accuracy and macro F1 ≥0.90; no >0.02 regression; identical benchmark hashes |
| Review decision | Record the actual gate, decision, reviewer and time |
| Serving location | Record local run, Azure version/deployment, or AWS package/config/endpoint |
| Rollback target | Record the prior approved release and runtime |
| Monitoring | Platform errors/latency; input means; delayed-label accuracy by version |

## Limitations

Iris is small and curated. These scores do not establish performance on new
flower populations, cameras, sensors or other species. Each held-out species has
only ten examples; small differences are uncertain. The model does not detect
unknown species, guarantee calibrated probabilities, or provide a fairness or
robustness assessment. Broad numeric validation does not prove biological
plausibility. Do not use it for consequential decisions.

The six rows in `examples/new-labels.csv` are invented teaching examples.
Simulated monitoring traffic is not independent evidence of generalization.

## Release evidence

Attach or reference your run directory, gate, optional final test report, exported
release, source commit/hash, image digest, smoke response, monitoring window,
approval record and cleanup outcome. Document live cloud checks separately from
offline SDK tests. Keep the actual deployment metadata with the release so that
model identity is recoverable after a terminal or notebook is closed.
