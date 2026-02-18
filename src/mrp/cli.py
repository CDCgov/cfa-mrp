"""CLI entry point — mrp run."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mrp.orchestrator import DefaultOrchestrator, Orchestrator


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


def _apply_cli_args(orch: Orchestrator, args: argparse.Namespace) -> None:
    """Set orchestrator attrs from parsed CLI args."""
    skip = {"command", "config", "overrides", "output_dir", "profile"}
    for key, value in vars(args).items():
        if key not in skip and hasattr(orch, key):
            setattr(orch, key, value)


def main(
    argv: list[str] | None = None,
    orchestrator: Orchestrator | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="mrp", description="Model Run Protocol CLI")
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

    orch = orchestrator or DefaultOrchestrator()
    orch.add_arguments(run_parser)

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "run":
        return _run(args, orch)

    return 0


def _run(args: argparse.Namespace, orch: Orchestrator) -> int:
    profiles = args.profile or {}
    runtime_profile = profiles.get("runtime")

    if isinstance(orch, DefaultOrchestrator):
        orch.output_dir = args.output_dir
        orch.output_profile = profiles.get("output")

    _apply_cli_args(orch, args)

    config = orch.load_config(args.config, overrides=args.overrides or None)
    runtime = orch.resolve_runtime(config, runtime_profile=runtime_profile)
    result = orch.execute(config, runtime)

    if not result.ok:
        stderr_text = result.stderr.decode(errors="replace").strip()
        print(f"FAILED (exit {result.exit_code}): {stderr_text}", file=sys.stderr)
        return 1

    if result.stdout:
        sys.stdout.buffer.write(result.stdout)

    print("Run completed successfully", file=sys.stderr)
    return 0
