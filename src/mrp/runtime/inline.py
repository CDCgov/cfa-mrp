"""Inline runtime adapter — calls Python callables directly."""

from __future__ import annotations

import io
import sys
import traceback
from collections.abc import Callable
from typing import Any

from mrp.runtime.base import RunResult, Runtime


class InlineRuntime(Runtime):
    def __init__(self, fn: Callable):
        self.fn = fn

    def run(self, run_json: dict[str, Any]) -> RunResult:
        self._prepare_output(run_json)

        stdout_buf = io.BytesIO()
        stderr_buf = io.BytesIO()

        # Wrap byte buffers with TextIOWrapper for text-mode code
        stdout_text = io.TextIOWrapper(stdout_buf, encoding="utf-8")
        stderr_text = io.TextIOWrapper(stderr_buf, encoding="utf-8")

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        try:
            sys.stdout = stdout_text
            sys.stderr = stderr_text
            self.fn(run_json)
            exit_code = 0
        except SystemExit as e:
            exit_code = e.code if isinstance(e.code, int) else 1
        except Exception:
            stderr_text.write(traceback.format_exc())
            exit_code = 1
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        stdout_text.flush()
        stderr_text.flush()

        return RunResult(
            exit_code=exit_code,
            stdout=stdout_buf.getvalue(),
            stderr=stderr_buf.getvalue(),
        )
