"""Write or verify the committed OpenAPI contract snapshot."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

os.chdir(Path(__file__).resolve().parents[1])

from app.core.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402

SNAPSHOT = Path(__file__).resolve().parents[1] / "openapi.json"


def rendered_contract() -> str:
    application = create_app(get_settings())
    return json.dumps(application.openapi(), indent=2, sort_keys=True) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the committed snapshot differs from the application contract",
    )
    args = parser.parse_args()
    rendered = rendered_contract()
    if args.check:
        if not SNAPSHOT.exists():
            raise SystemExit(f"Missing OpenAPI snapshot: {SNAPSHOT}")
        if SNAPSHOT.read_text(encoding="utf-8") != rendered:
            raise SystemExit(
                "OpenAPI snapshot is stale. Run `python scripts/export_openapi.py` "
                "from backend/ and commit the result."
            )
        print("OpenAPI snapshot is current.")
        return
    SNAPSHOT.write_text(rendered, encoding="utf-8")
    print(f"Wrote {SNAPSHOT}")


if __name__ == "__main__":
    main()
