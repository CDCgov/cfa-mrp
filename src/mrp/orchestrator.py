"""Orchestrator — plugin that hooks into arg parsing, config, and execution."""

from __future__ import annotations

import argparse
import copy
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from mrp.config import apply_overrides, build_run_json, load_toml
from mrp.runtime import RunResult, Runtime
from mrp.runtime import resolve_runtime as _resolve_runtime
from mrp.stager import cleanup, stage_files


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> None:
    for key, value in updates.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _load_single_config(config: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(config, (str, Path)):
        path = Path(config)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        return load_toml(path)
    elif isinstance(config, dict):
        return copy.deepcopy(config)
    else:
        raise TypeError(
            f"config must be a str, Path, or dict, got {type(config).__name__}"
        )


class Orchestrator(ABC):
    """Base class for orchestrators.

    Subclass and override ``execute()`` to control how a model is
    executed. Use ``self.build_run()`` to turn config into run_json and
    ``self.run()`` to execute it.
    """

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add custom CLI arguments. Default: no-op."""
        pass

    def load_config(
        self,
        *configs: str | Path | dict[str, Any],
        overrides: list[str] | None = None,
    ) -> dict[str, Any]:
        """Load/merge configs. Handles paths, dicts, --set overrides."""
        if not configs:
            raise ValueError("At least one config is required")

        result = _load_single_config(configs[0])
        for layer in configs[1:]:
            loaded = _load_single_config(layer)
            _deep_merge(result, loaded)

        if overrides:
            result = apply_overrides(result, overrides)

        return result

    def resolve_runtime(
        self,
        config: dict[str, Any],
        *,
        runtime_profile: str | None = None,
    ) -> Runtime | None:
        """Returns None if no [runtime] section."""
        if not config.get("runtime"):
            return None
        return _resolve_runtime(config, runtime_profile=runtime_profile)

    @abstractmethod
    def execute(self, config: dict[str, Any], runtime: Runtime | None) -> RunResult:
        """Execute the orchestration.

        Call self.build_run() to create run_json, then self.run() to
        execute it. runtime is None when config has no [runtime] section.
        """
        ...

    def build_run(
        self,
        config: dict[str, Any],
        *,
        output_dir: str | None = None,
        output_profile: str | None = None,
    ) -> dict[str, Any]:
        """Stage files and build run_json from config."""
        raw_files = config.get("model", {}).get("files", {})
        staged_files = stage_files(raw_files) if raw_files else {}
        return build_run_json(
            config,
            staged_files=staged_files,
            output_dir=output_dir,
            output_profile=output_profile,
        )

    def run(self, run_json: dict[str, Any], runtime: Runtime) -> RunResult:
        """Execute run_json via runtime, then clean up staged files."""
        try:
            return runtime.run(run_json)
        finally:
            cleanup()


class DefaultOrchestrator(Orchestrator):
    """Builds run_json and executes a single run."""

    def __init__(
        self,
        *,
        output_dir: str | None = None,
        output_profile: str | None = None,
    ):
        self.output_dir = output_dir
        self.output_profile = output_profile

    def execute(self, config: dict[str, Any], runtime: Runtime | None) -> RunResult:
        if runtime is None:
            raise ValueError("DefaultOrchestrator requires a runtime")
        run_json = self.build_run(
            config,
            output_dir=self.output_dir,
            output_profile=self.output_profile,
        )
        return self.run(run_json, runtime)
