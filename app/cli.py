"""WISPGen CLI entry points."""

import argparse
import sys


def seed_demo() -> None:
    """Placeholder for the demo tenant seed command."""
    print("seed-demo: placeholder — implemented in Task 09")


def main(argv: list[str] | None = None) -> int:
    """Run the WISPGen CLI."""
    parser = argparse.ArgumentParser(prog="wispgen")
    subparsers = parser.add_subparsers(dest="command")

    seed_parser = subparsers.add_parser("seed-demo", help="Seed the demo tenant")
    seed_parser.set_defaults(func=seed_demo)

    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 1

    args.func()
    return 0


if __name__ == "__main__":
    sys.exit(main())
