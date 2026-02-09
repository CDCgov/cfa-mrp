"""Orchestrator — sits between translation and runtime execution."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from mrp.runtime import RunResult, resolve_runtime


class Orchestrator(ABC):
    """Base class for orchestrators.

    An orchestrator receives the built transport JSON and the original
    config (with all profiles and orchestration keys intact), then
    decides how to spawn and call runtimes.
    """

    @abstractmethod
    def run(self, run_json: dict[str, Any], config: dict[str, Any]) -> RunResult:
        """Execute a model run.

        Args:
            run_json: Built transport JSON (command/args already stripped).
            config: Original parsed config with all profiles and
                orchestration keys (command, args) still present.
        """
        ...


class DefaultOrchestrator(Orchestrator):
    """Resolves a single runtime from config and executes."""

    def __init__(self, runtime_profile: str | None = None):
        self.runtime_profile = runtime_profile

    def run(self, run_json: dict[str, Any], config: dict[str, Any]) -> RunResult:
        runtime = resolve_runtime(config, runtime_profile=self.runtime_profile)
        return runtime.run(run_json)
