# MLOps basics: local → Azure → AWS

A practical course built around one small Iris classifier. Learn to validate
data, record experiments, evaluate and promote models, serve predictions,
monitor behavior, retrain, and roll back releases.

**Start with the [20-minute local walkthrough](docs/quickstart.md)**. Then use the
[course guide](docs/00-course-guide.md) for the complete lesson sequence.

```bash
cd python
uv sync --locked
uv run jupyter lab notebooks/iris.ipynb
```

Reusable scripts live in `python/src/iris_mlops/`; exploration lives in
`python/notebooks/`. [The Python guide](python/README.md) maps each short command
to its source file. You only need basic Python for the first lessons; cloud
identity, permissions and resource management are introduced after the local loop.

The cloud lessons use **Azure Machine Learning** and **Amazon SageMaker AI**.
Setup templates and runnable scripts are included. Cloud resources are created
only when you run the cloud steps; follow each lesson's cleanup section.

| Directory | Contents |
| --- | --- |
| [docs/](docs/00-course-guide.md) | Lessons, operational runbooks, and capstone |
| [python/](python/README.md) | uv project, scripts, notebooks, API, and tests |
| [cloud/azure/](cloud/azure/) | Azure resource setup and monitoring queries |
| [cloud/aws/](cloud/aws/) | AWS infrastructure template and monitoring queries |
| [.github/workflows/](.github/workflows/) | Automated local verification |

See the [documentation review](docs/documentation-review.md) for verified platform
choices, sources, and the limits of local validation.
