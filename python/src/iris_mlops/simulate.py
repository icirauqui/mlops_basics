"""Send synthetic lesson traffic and save delayed labels for monitoring."""

import argparse
import json
import urllib.request
from pathlib import Path

from iris_mlops.data import DATA_DIR, FEATURES, validate_data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080/predict")
    parser.add_argument("--data", type=Path, default=DATA_DIR)
    parser.add_argument(
        "--shift", type=float, default=0.0, help="Artificial petal-length shift in cm"
    )
    parser.add_argument("--feedback", type=Path, default=Path("state/feedback.jsonl"))
    args = parser.parse_args()
    # This is a simulation from training rows, not a production accuracy estimate.
    frame = validate_data(args.data)["train"].copy()
    frame["petal_length"] += args.shift
    args.feedback.parent.mkdir(parents=True, exist_ok=True)
    for start in range(0, len(frame), 10):
        batch = frame.iloc[start : start + 10]
        request = urllib.request.Request(
            args.url,
            data=json.dumps({"instances": batch[FEATURES].to_dict("records")}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
        with args.feedback.open("a", encoding="utf-8") as handle:
            for index, label in enumerate(batch.label):
                handle.write(
                    json.dumps(
                        {
                            "request_id": result["request_id"],
                            "row_index": index,
                            "label": label,
                        }
                    )
                    + "\n"
                )
    print(f"Sent {len(frame)} synthetic examples; labels saved to {args.feedback}")


if __name__ == "__main__":
    main()
