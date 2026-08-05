"""CLI for deployment config helpers.

Usage:
    python -m deploy.config.cli load --env production
    python -m deploy.config.cli validate --env production
"""

from __future__ import annotations

import argparse
import json
import sys

from deploy.config.loader import load_environment, validate_production


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="deploy-config")
    sub = parser.add_subparsers(dest="command", required=True)

    load_cmd = sub.add_parser("load", help="Load an environment profile")
    load_cmd.add_argument("--env", default="production")

    validate_cmd = sub.add_parser("validate", help="Validate production secrets")
    validate_cmd.add_argument("--env", default="production")
    validate_cmd.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "load":
        values = load_environment(args.env)
        for key in sorted(values):
            if any(secret in key for secret in ("KEY", "PASSWORD", "SECRET")):
                continue
            print(f"{key}={values[key]}")
        return 0

    values = load_environment(args.env)
    errors = validate_production(values)
    if args.json:
        print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
    else:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        if not errors:
            print("OK: environment secrets valid")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
