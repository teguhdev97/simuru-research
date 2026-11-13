from __future__ import annotations

import argparse
import json

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
    print(json.dumps(result.__dict__ if hasattr(result, "__dict__") else {
        "target_url": result.target_url,
        "title": result.title,
        "username_field_found": result.username_field_found,
        "email_field_found": result.email_field_found,
        "password_field_found": result.password_field_found,
        "submit_button_found": result.submit_button_found,
    }, indent=2))


if __name__ == "__main__":
    main()
