"""Programmatic API — run models from Python code."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from mrp.config import build_run_json, load_toml
from mrp.orchestrator import DefaultOrchestrator, Orchestrator
from mrp.runtime import RunResult
from mrp.stager import cleanup, stage_files


def apply_dict_overrides(
    config: dict[str, Any], overrides: dict[str, Any]
) -> dict[str, Any]:
    """Deep-merge *overrides* into *config*, returning a new dict."""
    config = copy.deepcopy(config)
    _deep_merge(config, overrides)
    return config


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> None:
    for key, value in updates.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def run(
    config: str | Path | dict[str, Any],
    *,
    overrides: dict[str, Any] | None = None,
    output_dir: str | None = None,
    orchestrator: Orchestrator | None = None,
    runtime_profile: str | None = None,
    output_profile: str | None = None,
) -> RunResult:
    """Run a model and return the result.

    Args:
        config: Path to a TOML config file (str or Path), or a pre-loaded
            config dict matching the MRP transport structure.
        overrides: Nested dict of config overrides, deep-merged into config.
            Example: ``{"input": {"r0": 3.0, "sim_length": 100}}``
        output_dir: Override the output directory for filesystem output.
        orchestrator: A pre-instantiated Orchestrator to control runtime
            selection and execution. Mutually exclusive with runtime_profile.
        runtime_profile: Name of the runtime profile to select.
        output_profile: Name of the output profile to select.

    Returns:
        RunResult with exit_code, stdout (bytes), stderr (bytes), and ok property.

    Raises:
        FileNotFoundError: If config is a path that does not exist.
        TypeError: If config is not a str, Path, or dict.
        ValueError: If runtime configuration is invalid, or if both
            orchestrator and runtime_profile are specified.
    """
    if isinstance(config, (str, Path)):
        path = Path(config)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        loaded = load_toml(path)
    elif isinstance(config, dict):
        loaded = copy.deepcopy(config)
    else:
        raise TypeError(
            f"config must be a str, Path, or dict, got {type(config).__name__}"
        )

    if overrides:
        loaded = apply_dict_overrides(loaded, overrides)

    try:
        raw_files = loaded.get("model", {}).get("files", {})
        staged_files = stage_files(raw_files) if raw_files else {}

        run_json = build_run_json(
            loaded,
            staged_files=staged_files,
            output_dir=output_dir,
            output_profile=output_profile,
        )

        if orchestrator is not None and runtime_profile is not None:
            raise ValueError(
                "Cannot specify both 'orchestrator' and 'runtime_profile'. "
                "Pass an Orchestrator instance or a profile name, not both."
            )

        orch = orchestrator or DefaultOrchestrator(runtime_profile=runtime_profile)
        return orch.run(run_json, loaded)
    finally:
        cleanup()
