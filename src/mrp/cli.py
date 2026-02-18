"""CLI entry point — mrp run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from mrp.config import parse_value
from mrp.orchestrator import DefaultOrchestrator, Orchestrator


def _parse_input(value: str) -> dict[str, Any]:
    """Parse a single --input value into a dict.

    Accepts:
      - A path to a JSON file (e.g. "params.json")
      - An inline JSON object (e.g. '{"r0": 3.0}')
      - A key=value pair (e.g. "r0=3.0")
    """
    stripped = value.strip()

    # Inline JSON object
    if stripped.startswith("{"):
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError as e:
            raise argparse.ArgumentTypeError(f"Invalid JSON: {e}") from e
        if not isinstance(obj, dict):
            raise argparse.ArgumentTypeError("--input JSON must be an object")
        return obj

    # key=value pair
    if "=" in stripped and not stripped.endswith(".json"):
        key, _, val = stripped.partition("=")
        return {key.strip(): parse_value(val.strip())}

    # File path
    path = Path(stripped)
    if not path.exists():
        raise argparse.ArgumentTypeError(f"File not found: {path}")
    with open(path) as f:
        try:
            obj = json.load(f)
        except json.JSONDecodeError as e:
            raise argparse.ArgumentTypeError(f"Invalid JSON in {path}: {e}") from e
    if not isinstance(obj, dict):
        raise argparse.ArgumentTypeError(
            f"--input file must contain a JSON object, got {type(obj).__name__}"
        )
    return obj


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
    skip = {"command", "config", "overrides", "output_dir", "profile", "input_values"}
    for key, value in vars(args).items():
        if key not in skip and hasattr(orch, key):
            setattr(orch, key, value)


def _resolve_config_path(raw: str) -> Path:
    """Resolve a config argument to a file path.

    Accepts a direct path (e.g. "mrp.toml") or a short name
    (e.g. "renewal") which expands to "renewal.mrp.toml".
    """
    path = Path(raw)
    if path.exists():
        return path
    # Try [name].mrp.toml convention
    named = Path(f"{raw}.mrp.toml")
    if named.exists():
        return named
    # Return original so argparse gives a useful error downstream
    return path


_SUBCOMMANDS = {"run"}


def main(
    argv: list[str] | None = None,
    orchestrator: Orchestrator | None = None,
) -> int:
    # Default command: treat bare `mrp <config> ...` as `mrp run <config> ...`
    effective = argv if argv is not None else sys.argv[1:]
    if effective and effective[0] not in _SUBCOMMANDS and not effective[0].startswith("-"):
        effective = ["run", *effective]

    parser = argparse.ArgumentParser(prog="mrp", description="Model Run Protocol CLI")
    sub = parser.add_subparsers(dest="command")

    run_parser = sub.add_parser("run", help="Run a model from a TOML config")
    run_parser.add_argument(
        "config", type=_resolve_config_path, help="Config file or name ([name].mrp.toml)"
    )
    run_parser.add_argument(
        "--set",
        dest="overrides",
        action="append",
        default=[],
        help="Override config values (e.g. --set input.r0=3.0)",
    )
    run_parser.add_argument(
        "--input",
        dest="input_values",
        action="append",
        default=[],
        help=(
            "Set input values. Accepts a JSON file path, "
            "inline JSON object, or key=value pair. "
            "Can be repeated. (e.g. --input params.json, "
            "--input '{\"r0\": 3.0}', --input r0=3.0)"
        ),
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

    args = parser.parse_args(effective)

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "run":
        return _run(args, orch)

    return 0


def _log_inputs(
    config: dict[str, Any],
    config_path: Path,
    overrides: list[str],
    input_args: list[str],
) -> None:
    """Log resolved inputs and their sources to stderr."""
    inputs = config.get("input", {})
    if not inputs:
        print("Running model with no inputs", file=sys.stderr)
        return

    set_keys: set[str] = set()
    for o in overrides:
        key, _, _ = o.partition("=")
        parts = key.strip().split(".")
        if len(parts) >= 2 and parts[0] == "input":
            set_keys.add(parts[1])

    input_keys: set[str] = set()
    for raw in input_args:
        parsed = _parse_input(raw)
        input_keys.update(parsed.keys())

    # Group keys by source, preserving original order
    from_file: dict[str, Any] = {}
    from_set: dict[str, Any] = {}
    from_input: dict[str, Any] = {}
    for key, value in inputs.items():
        if key in input_keys:
            from_input[key] = value
        elif key in set_keys:
            from_set[key] = value
        else:
            from_file[key] = value

    print("Running model with inputs", file=sys.stderr)
    for section, label in [
        (from_file, f"from {config_path}"),
        (from_set, "from --set"),
        (from_input, "from --input"),
    ]:
        if section:
            print(f"  {label}:", file=sys.stderr)
            for key, value in section.items():
                print(f"    {key}: {value!r}", file=sys.stderr)


def _run(args: argparse.Namespace, orch: Orchestrator) -> int:
    profiles = args.profile or {}
    runtime_profile = profiles.get("runtime")

    if isinstance(orch, DefaultOrchestrator):
        orch.output_dir = args.output_dir
        orch.output_profile = profiles.get("output")

    _apply_cli_args(orch, args)

    config = orch.load_config(args.config, overrides=args.overrides or None)

    # Merge --input values into config["input"]
    for raw in args.input_values:
        parsed = _parse_input(raw)
        config.setdefault("input", {}).update(parsed)

    _log_inputs(config, args.config, args.overrides or [], args.input_values)

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
