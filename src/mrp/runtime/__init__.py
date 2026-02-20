"""Runtime adapters — bridge the abstract model interface to concrete mechanisms."""

from __future__ import annotations

import importlib
from typing import Any

from mrp.config import _select_profile
from mrp.runtime.base import RunResult, Runtime

__all__ = ["RunResult", "Runtime", "resolve_runtime"]


def _resolve_callable(dotted_path: str):
    """Resolve a dotted path like 'pkg.module:func' to a callable."""
    module_path, _, attr = dotted_path.partition(":")
    if not attr:
        raise ValueError(
            f"Invalid callable path '{dotted_path}': expected 'module:attr' format"
        )
    module = importlib.import_module(module_path)
    return getattr(module, attr)


def resolve_runtime(
    config: dict[str, Any],
    *,
    runtime_profile: str | None = None,
) -> Runtime:
    """Factory: build the right Runtime adapter from config."""
    runtime = config.get("runtime", {})
    selected = _select_profile(runtime, runtime_profile, section_name="runtime")

    spec = selected.get("spec", "process")

    if spec == "process":
        from mrp.runtime.subprocess import SubprocessRuntime

        command = selected.get("command")
        if not command:
            raise ValueError("runtime.command is required for process runtime")
        args = selected.get("args", [])
        full_command = [command] + args

        env = selected.get("env")
        if env == "uv":
            full_command = ["uv", "run"] + full_command
        elif env is not None:
            raise ValueError(f"Unknown runtime env: {env!r}")

        return SubprocessRuntime(
            command=full_command,
            cwd=selected.get("cwd"),
            timeout=selected.get("timeout"),
        )

    if spec == "inline":
        from mrp.runtime.inline import InlineRuntime

        callable_path = selected.get("callable")
        if not callable_path:
            raise ValueError("runtime.callable is required for inline runtime")
        fn = _resolve_callable(callable_path)
        return InlineRuntime(fn=fn)

    raise ValueError(f"Unknown runtime spec: {spec!r}")
