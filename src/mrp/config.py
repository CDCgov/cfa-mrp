"""TOML parsing and JSON transport translation."""

from __future__ import annotations

import copy
import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any


def load_toml(path: Path) -> dict[str, Any]:
    with open(path, "rb") as f:
        return tomllib.load(f)


def apply_overrides(config: dict[str, Any], overrides: list[str]) -> dict[str, Any]:
    """Apply --set key=value overrides using dotted paths."""
    config = copy.deepcopy(config)
    for override in overrides:
        key, _, value = override.partition("=")
        if not value:
            raise ValueError(f"Invalid override (missing '='): {override}")

        parts = key.strip().split(".")
        target = config
        for part in parts[:-1]:
            target = target.setdefault(part, {})

        target[parts[-1]] = parse_value(value.strip())

    return config


def parse_value(value: str) -> Any:
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def resolve_input(
    config: dict[str, Any], base_dir: Path | None = None
) -> dict[str, Any]:
    """If input is a file path string, load the JSON file."""
    raw = config.get("input")
    if not isinstance(raw, str):
        return config
    config = copy.deepcopy(config)
    path = Path(raw)
    if base_dir and not path.is_absolute():
        path = base_dir / path
    with open(path) as f:
        config["input"] = json.load(f)
    return config


def _select_profile(
    section: dict[str, Any], profile_name: str | None
) -> dict[str, Any]:
    """Select a profile from a section, or return the section as-is if no profiles."""
    profiles = section.get("profile")
    if not profiles:
        return section

    if profile_name and profile_name in profiles:
        return dict(profiles[profile_name])

    # Default: use "default" profile if present, otherwise first key
    if "default" in profiles:
        return dict(profiles["default"])

    first_key = next(iter(profiles))
    return dict(profiles[first_key])


def build_run_json(
    config: dict[str, Any],
    *,
    staged_files: dict[str, str] | None = None,
    output_dir: str | None = None,
    output_profile: str | None = None,
) -> dict[str, Any]:
    """Build a single-run JSON transport object from parsed config.

    The config dict mirrors the JSON transport structure. This function
    deep-copies it, strips orchestration-only keys, and injects
    per-run values (mrp metadata, output paths).
    """
    result = copy.deepcopy(config)

    # Strip command/args from runtime (flat or profiled)
    runtime = result.get("runtime", {})
    profiles = runtime.get("profile")
    if profiles:
        for prof in profiles.values():
            prof.pop("command", None)
            prof.pop("args", None)
    else:
        runtime.pop("command", None)
        runtime.pop("args", None)

    # Staged files override raw URIs
    if staged_files:
        result.setdefault("model", {})["files"] = staged_files

    # Default to stdout output
    if "output" not in result:
        result["output"] = {"spec": "stdout"}

    # Override filesystem output dir if requested
    output = result.get("output", {})
    output_section = _select_profile(output, output_profile)

    if output_section.get("spec") == "filesystem" and output_dir:
        if output.get("profile"):
            target_name = output_profile or (
                "default"
                if "default" in output["profile"]
                else next(iter(output["profile"]))
            )
            output["profile"][target_name]["dir"] = output_dir
        else:
            output["dir"] = output_dir

    # Compute input_hash from the transport (excluding mrp section)
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":"))
    input_hash = hashlib.sha256(canonical.encode()).hexdigest()[:16]
    result["mrp"] = {"version": "0.0.1", "input_hash": input_hash}

    return result
