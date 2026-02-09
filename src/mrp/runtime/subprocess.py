"""Subprocess runtime adapter — invokes models via stdin/stdout."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from mrp.runtime.base import RunResult, Runtime


class SubprocessRuntime(Runtime):
    def __init__(
        self,
        command: list[str],
        *,
        cwd: str | Path | None = None,
        timeout: int | None = None,
    ):
        self.command = command
        self.cwd = cwd
        self.timeout = timeout

    def run(self, run_json: dict[str, Any]) -> RunResult:
        self._prepare_output(run_json)

        input_bytes = json.dumps(run_json).encode()

        result = subprocess.run(
            self.command,
            input=input_bytes,
            capture_output=True,
            cwd=self.cwd,
            timeout=self.timeout,
        )

        return RunResult(
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )
