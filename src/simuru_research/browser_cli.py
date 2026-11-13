from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from simuru_research.engine.browser_form_qa import inspect_registration_form
from simuru_research.engine.browser_session_qa import run_sequential_browser_sessions


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run guarded browser QA on an allowlisted site you own or may test."
    )
    parser.add_argument("--url", required=True, help="Local or explicitly allowlisted QA URL")
    parser.add_argument("--timeout", type=int, default=20, help="Page wait timeout in seconds")
    parser.add_argument(
        "--mode",
        choices=("inspect", "sessions"),
        default="inspect",
        help="Inspect form controls or open sequential temporary Chrome sessions",
    )
    parser.add_argument(
        "--sessions",
        type=int,
        default=1,
        help="Number of sequential sessions for --mode sessions (1-20)",
    )
    parser.add_argument(
        "--headless", action="store_true", help="Use headless Chrome (inspect only)"
    )
    args = parser.parse_args()

    if args.mode == "inspect":
        result = inspect_registration_form(
            args.url,
            timeout_seconds=min(args.timeout, 60),
            headless=args.headless,
        )
        print(json.dumps(asdict(result), indent=2))
        return

    if args.headless:
        parser.error("--headless is only supported with --mode inspect.")
    results = run_sequential_browser_sessions(
        args.url,
        sessions=args.sessions,
        timeout_seconds=args.timeout,
    )
    print(json.dumps([asdict(item) for item in results], indent=2))


if __name__ == "__main__":
    main()
