"""Dump the FastAPI OpenAPI schema for the TypeScript drift check.

Usage: python scripts/dump_openapi.py [output.json]
"""

import json
import sys
from pathlib import Path


def main() -> None:
    """Write the app's OpenAPI schema to one JSON file."""
    api_dir = Path(__file__).resolve().parent.parent / "api"
    sys.path.insert(0, str(api_dir))
    from strompilot.main import app

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("openapi.json")
    target.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {target} ({len(app.openapi()['paths'])} paths)")


if __name__ == "__main__":
    main()
