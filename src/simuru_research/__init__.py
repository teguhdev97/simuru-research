"""Simuru Research: read-only API checks and local sandbox QA."""

__version__ = "0.6.0"


def main() -> None:
    """Run the command-line interface."""
    from simuru_research.cli import main as cli_main

    cli_main()
