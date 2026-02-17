"""Programmatic API — run models from Python code."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from mrp.orchestrator import DefaultOrchestrator, Orchestrator
from mrp.runtime import RunResult


def apply_dict_overrides(
    config: dict[str, Any], overrides: dict[str, Any]
) -> dict[str, Any]:
    """Deep-merge *overrides* into *config*, returning a new dict."""
    from mrp.orchestrator import _deep_merge

    config = copy.deepcopy(config)
    _deep_merge(config, overrides)
    return config


def run(
    *configs: str | Path | dict[str, Any],
    output_dir: str | None = None,
    orchestrator: Orchestrator | None = None,
    runtime_profile: str | None = None,
    output_profile: str | None = None,
) -> RunResult:
    """Run a model and return the result.

    Args:
        *configs: One or more config sources (paths or dicts), deep-merged
            left to right. Later configs override earlier ones.
        output_dir: Override the output directory for filesystem output.
        orchestrator: A pre-instantiated Orchestrator to control execution.
        runtime_profile: Name of the runtime profile to select.
        output_profile: Name of the output profile to select.

    Returns:
        RunResult with exit_code, stdout (bytes), stderr (bytes), and ok
        property.

    Raises:
        FileNotFoundError: If a config path does not exist.
        TypeError: If a config is not a str, Path, or dict.
        ValueError: If no configs are provided.
    """
    orch = orchestrator or DefaultOrchestrator(
        output_dir=output_dir,
        output_profile=output_profile,
    )
    config = orch.load_config(*configs)
    runtime = orch.resolve_runtime(config, runtime_profile=runtime_profile)
    return orch.execute(config, runtime)
