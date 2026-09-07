# Lesson 01: Train an Iris classifier

This lesson takes a small dataset through training, evaluation, saving, and
prediction. Everything runs locally on a CPU.

This is the introductory example. [Lesson 02](02-data-and-experiments.md)
introduces a separate 60/20/20 lifecycle dataset and versioned runs; the scripts
in this lesson remain available as the simplest starting point.

## Dataset

We use the [Iris dataset bundled with scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_iris.html).
It contains 150 flowers: 50 each of **setosa**, **versicolor**, and **virginica**.
Each row has four measurements in centimeters, in this order:

1. Sepal length
2. Sepal width
3. Petal length
4. Petal width

The target is the species, encoded as `0` (setosa), `1` (versicolor), or
`2` (virginica). `load_iris(as_frame=True)` returns the measurements as a pandas
DataFrame. The dataset has no missing values and needs no separate download.

## Model and training

We use **logistic regression**, a simple classification model that estimates a
probability for each species. Despite its name, it is used for classification.

The script splits the rows into **120 training examples** and **30 test examples**.
Stratification keeps the species balanced in each set; `random_state=42` makes
the split repeatable.

A scikit-learn pipeline first standardizes each feature with `StandardScaler`,
then fits `LogisticRegression(C=1.0, max_iter=200)`. Scaling learns the mean and
standard deviation from training data only. The same fitted transformation is
applied automatically during prediction, keeping test data out of training.
`C` controls regularization: smaller values mean stronger regularization.

Evaluation uses the held-out test set:

- **Accuracy**: fraction of flowers classified correctly.
- **Precision**: among predictions of a species, how many are correct.
- **Recall**: among actual flowers of a species, how many are found.
- **F1**: harmonic mean of precision and recall.
- **Support**: number of test flowers belonging to each species.

The notebook also plots a confusion matrix: rows are actual species and columns
are predictions. Correct predictions appear on the diagonal.

## Set up and run

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if needed.
From the repository root:

```bash
cd python
uv sync --locked
uv run python -m iris_mlops.train
uv run python -m iris_mlops.predict 5.1 3.5 1.4 0.2
```

`uv` creates `.venv` and installs the dependencies from `uv.lock`. The project
selects Python 3.12 through `.python-version`; uv can download it if needed.
The first setup requires internet access. No manual environment activation is
needed when using `uv run`.

Training creates `python/artifacts/model.joblib` (the scaler and classifier
together) and `python/artifacts/metrics.json` (test scores). Running training again
overwrites these files. They are ignored by Git because they can be regenerated.
Only load model files you trust: joblib files can execute code when loaded.

## Explore in Jupyter

From `python/`, run:

```bash
uv run jupyter lab notebooks/iris.ipynb
```

Select the Python 3 kernel and run the cells from top to bottom. In VS Code,
select `python/.venv/bin/python` as the notebook interpreter instead.
The notebook imports the functions from `iris_mlops.train`, shows dataset summaries and
a scatter plot, trains the model, displays scores and a confusion matrix, and
lets you inspect individual predictions. Saving artifacts is an optional final
cell, so exploration does not automatically replace the command-line model.

Change the notebook's `C` setting to explore regularization, then rerun the
training and evaluation cells. This small test set is useful for learning, but
repeatedly choosing settings based on its score biases the evaluation. For a
later tuning exercise, use cross-validation on training data and reserve the
test set for a final check. A good Iris score does not establish production
readiness.

## Files

```text
docs/01-iris-training.md
python/
  .python-version
  pyproject.toml
  uv.lock
  README.md
  src/iris_mlops/train.py
  src/iris_mlops/predict.py
  notebooks/iris.ipynb
  artifacts/             # generated locally
```

The [uv project guide](https://docs.astral.sh/uv/guides/projects/) explains the
environment and lockfile workflow in more detail.

**Done when:** the script and notebook train successfully, you can name the four
features, and the example prediction returns setosa.

Next: [data and experiments](02-data-and-experiments.md).
