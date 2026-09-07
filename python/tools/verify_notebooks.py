"""Execute local notebook cells; skip cells explicitly tagged 'cloud'."""

from pathlib import Path

import nbformat
from nbclient import NotebookClient


def main():
    base = Path(__file__).resolve().parents[1] / "notebooks"
    output = base / "executed"
    output.mkdir(exist_ok=True)
    for source in sorted(base.glob("*.ipynb")):
        notebook = nbformat.read(source, as_version=4)
        nbformat.validate(notebook)
        NotebookClient(
            notebook,
            timeout=120,
            kernel_name="python3",
            skip_cells_with_tag="cloud",
            resources={"metadata": {"path": str(base)}},
        ).execute()
        nbformat.write(notebook, output / source.name)
        print(f"Executed local cells: {source.name}", flush=True)


if __name__ == "__main__":
    main()
