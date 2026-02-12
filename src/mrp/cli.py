"""CLI entry point — mrp run."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mrp.config import apply_overrides, build_run_json, load_toml
from mrp.orchestrator import DefaultOrchestrator
from mrp.stager import cleanup, stage_files


def _parse_profiles(value: str) -> dict[str, str]:
    """Parse --profile 'runtime=local,output=default' into a dict."""
    result: dict[str, str] = {}
    for pair in value.split(","):
        key, _, val = pair.strip().partition("=")
        if not val:
            raise argparse.ArgumentTypeError(
                f"Invalid profile format: {pair!r}. Expected 'section=name'."
            )
        result[key.strip()] = val.strip()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mrp", description="Model Run Protocol CLI"
    )
    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="Run a model from a TOML config")
    run_parser.add_argument("config", type=Path, help="Path to TOML config file")
    run_parser.add_argument(
        "--set",
        dest="overrides",
        action="append",
        default=[],
        help="Override config values (e.g. --set input.r0=3.0)",
    )
    run_parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Override output directory",
    )
    run_parser.add_argument(
        "--profile",
        type=_parse_profiles,
        default=None,
        help="Select profiles (e.g. --profile runtime=local,output=default)",
    )

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "run":
        return _run(args)

    return 0


def _run(args: argparse.Namespace) -> int:
    if not args.config.exists():
        print(f"Error: config file not found: {args.config}", file=sys.stderr)
        return 1

    config = load_toml(args.config)

    if args.overrides:
        config = apply_overrides(config, args.overrides)

    profiles = args.profile or {}
    runtime_profile = profiles.get("runtime")
    output_profile = profiles.get("output")

    try:
        raw_files = config.get("model", {}).get("files", {})
        staged_files = stage_files(raw_files) if raw_files else {}

        run_json = build_run_json(
            config,
            staged_files=staged_files,
            output_dir=args.output_dir,
            output_profile=output_profile,
        )

        orchestrator = DefaultOrchestrator(runtime_profile=runtime_profile)
        result = orchestrator.run(run_json, config)
    finally:
        cleanup()

    if not result.ok:
        stderr_text = result.stderr.decode(errors="replace").strip()
        print(f"FAILED (exit {result.exit_code}): {stderr_text}", file=sys.stderr)
        return 1

    if result.stdout:
        sys.stdout.buffer.write(result.stdout)

    print("Run completed successfully", file=sys.stderr)
    return 0
