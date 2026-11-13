from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from simuru_research.engine.browser_form_qa import inspect_registration_form


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect a registration form on an allowlisted local/staging site."
    )
    parser.add_argument("--url", required=True, help="Local or allowlisted staging URL")
    parser.add_argument("--timeout", type=int, default=10, help="Page wait timeout (1-60)")
    parser.add_argument("--headless", action="store_true", help="Run Chrome without a window")
    args = parser.parse_args()

    result = inspect_registration_form(
        args.url,
        timeout_seconds=args.timeout,
        headless=args.headless,
    )
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
