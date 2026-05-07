"""
cli.py — Minimal command-line interface for OpenIA.

Entry point used by PyInstaller to build the ``openia`` desktop executable.

Usage
-----
    openia respond "help"
    openia respond "status"
    openia version
"""

from __future__ import annotations

import json
import sys


def main() -> None:
    """Console entry point for the ``openia`` command."""
    args = sys.argv[1:]

    if not args or args[0] in {"-h", "--help", "help"}:
        _print_help()
        return

    command = args[0]

    if command == "version":
        try:
            from importlib.metadata import PackageNotFoundError, version
            print(f"openia {version('openia')}")
        except PackageNotFoundError:
            print("openia 0.1.0")
        return

    if command == "respond":
        if len(args) < 2:
            print("Usage: openia respond <input_text>", file=sys.stderr)
            sys.exit(1)
        input_text = " ".join(args[1:])
        from openia import Agent, TransactionLog
        log = TransactionLog()
        agent = Agent(log=log)
        result = agent.respond(input_text)
        print(json.dumps(result, indent=2))
        return

    print(f"Unknown command: {command!r}", file=sys.stderr)
    _print_help()
    sys.exit(1)


def _print_help() -> None:
    print(
        "OpenIA — A reverse-engineered, dumbed-down, submissive AI\n"
        "\n"
        "Commands:\n"
        "  respond <text>   Ask the agent to respond to <text>\n"
        "  version          Print the OpenIA version\n"
        "  help             Show this message\n"
    )


if __name__ == "__main__":
    main()
