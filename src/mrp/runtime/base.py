"""Runtime base classes — RunResult and the Runtime ABC."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mrp.config import _select_profile


@dataclass
class RunResult:
    exit_code: int
    stdout: bytes
    stderr: bytes

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


class Runtime(ABC):
    """Base class for runtime adapters."""

    @abstractmethod
    def run(self, run_json: dict[str, Any]) -> RunResult: ...

    def _prepare_output(
        self, run_json: dict[str, Any], output_profile: str | None = None
    ):
        """Ensure filesystem output directory exists."""
        output = run_json.get("output", {})
        if output.get("spec") == "filesystem":
            out_dir = output.get("dir")
            if out_dir:
                Path(out_dir).mkdir(parents=True, exist_ok=True)
            return
        # Check profiled output
        profiles = output.get("profile")
        if profiles:
            selected = _select_profile(output, output_profile)
            if selected.get("spec") == "filesystem":
                out_dir = selected.get("dir")
                if out_dir:
                    Path(out_dir).mkdir(parents=True, exist_ok=True)
