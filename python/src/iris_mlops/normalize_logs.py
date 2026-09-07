"""Convert Azure/AWS exported console-message JSON into prediction JSONL."""

import argparse
import json
from pathlib import Path


def normalize(source, destination):
    messages = json.loads(Path(source).read_text())
    if not isinstance(messages, list):
        raise ValueError("Expected a JSON array of console message strings")
    events = {}
    for message in messages:
        try:
            event = json.loads(message)
        except (ValueError, TypeError):
            continue  # HTTP server startup messages are not prediction events.
        if isinstance(event, dict) and event.get("event") == "prediction":
            events[(event["model_version"], event["request_id"])] = event
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        "".join(json.dumps(event) + "\n" for event in events.values())
    )
    return len(events)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(
        f"Exported {normalize(args.source, args.destination)} unique prediction events"
    )


if __name__ == "__main__":
    main()
