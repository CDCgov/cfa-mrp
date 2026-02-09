from __future__ import annotations

import json
import sys

import pytest

from mrp.runtime import RunResult, resolve_runtime
from mrp.runtime.inline import InlineRuntime
from mrp.runtime.subprocess import SubprocessRuntime

# --- RunResult ---


class TestRunResult:
    def test_ok_when_zero(self):
        r = RunResult(exit_code=0, stdout=b"", stderr=b"")
        assert r.ok is True

    def test_not_ok_when_nonzero(self):
        r = RunResult(exit_code=1, stdout=b"", stderr=b"")
        assert r.ok is False

    def test_not_ok_when_negative(self):
        r = RunResult(exit_code=-9, stdout=b"", stderr=b"")
        assert r.ok is False

    def test_captures_stdout_and_stderr(self):
        r = RunResult(exit_code=0, stdout=b"out", stderr=b"err")
        assert r.stdout == b"out"
        assert r.stderr == b"err"


# --- helpers ---


def _run_json(*, output=None):
    """Build a minimal run JSON transport."""
    return {
        "mrp": {"version": "0.0.1", "input_hash": "test"},
        "runtime": {"spec": "process"},
        "model": {"spec": "test"},
        "input": {},
        "output": output or {"spec": "stdout"},
    }


# --- SubprocessRuntime ---


class TestSubprocessRuntime:
    def test_passes_json_on_stdin(self):
        transport = _run_json()
        script = "import sys,json; d=json.load(sys.stdin); print(d['model']['spec'])"
        rt = SubprocessRuntime([sys.executable, "-c", script])
        result = rt.run(transport)
        assert result.ok
        assert result.stdout.strip() == b"test"

    def test_captures_exit_code(self):
        rt = SubprocessRuntime([sys.executable, "-c", "raise SystemExit(2)"])
        result = rt.run(_run_json())
        assert result.exit_code == 2
        assert result.ok is False

    def test_captures_stderr(self):
        script = "import sys; print('oops', file=sys.stderr)"
        rt = SubprocessRuntime([sys.executable, "-c", script])
        result = rt.run(_run_json())
        assert result.ok
        assert b"oops" in result.stderr

    def test_creates_filesystem_output_dir(self, tmp_path):
        out_dir = tmp_path / "nested" / "output"
        transport = _run_json(output={"spec": "filesystem", "dir": str(out_dir)})
        rt = SubprocessRuntime([sys.executable, "-c", "pass"])
        result = rt.run(transport)
        assert result.ok
        assert out_dir.exists()

    def test_skips_non_filesystem_output(self, tmp_path):
        out_dir = tmp_path / "should_not_exist"
        transport = _run_json(output={"spec": "stdout", "dir": str(out_dir)})
        rt = SubprocessRuntime([sys.executable, "-c", "pass"])
        result = rt.run(transport)
        assert result.ok
        assert not out_dir.exists()

    def test_timeout(self):
        rt = SubprocessRuntime(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            timeout=1,
        )
        with pytest.raises(Exception):
            rt.run(_run_json())

    def test_cwd(self, tmp_path):
        rt = SubprocessRuntime(
            [sys.executable, "-c", "import os; print(os.getcwd())"],
            cwd=tmp_path,
        )
        result = rt.run(_run_json())
        assert result.ok
        assert result.stdout.decode().strip() == str(tmp_path)

    def test_model_writes_to_filesystem_sink(self, tmp_path):
        out_dir = tmp_path / "results"
        transport = _run_json(output={"spec": "filesystem", "dir": str(out_dir)})
        script = (
            "import sys, json; from pathlib import Path; "
            "d = json.load(sys.stdin); "
            "p = Path(d['output']['dir']); "
            "p.mkdir(parents=True, exist_ok=True); "
            "(p / 'out.txt').write_text('hello')"
        )
        rt = SubprocessRuntime([sys.executable, "-c", script])
        result = rt.run(transport)
        assert result.ok
        assert (out_dir / "out.txt").read_text() == "hello"


# --- InlineRuntime ---


def _noop_callable(run_json):
    pass


def _printing_callable(run_json):
    print("hello from inline")


def _stderr_callable(run_json):
    import sys

    print("warning", file=sys.stderr)


def _failing_callable(run_json):
    raise ValueError("boom")


def _exit_callable(run_json):
    raise SystemExit(42)


def _reads_model_spec(run_json):
    print(run_json["model"]["spec"])


class TestInlineRuntime:
    def test_success(self):
        rt = InlineRuntime(fn=_noop_callable)
        result = rt.run(_run_json())
        assert result.ok
        assert result.exit_code == 0

    def test_captures_stdout(self):
        rt = InlineRuntime(fn=_printing_callable)
        result = rt.run(_run_json())
        assert result.ok
        assert b"hello from inline" in result.stdout

    def test_captures_stderr(self):
        rt = InlineRuntime(fn=_stderr_callable)
        result = rt.run(_run_json())
        assert result.ok
        assert b"warning" in result.stderr

    def test_exception_returns_exit_code_1(self):
        rt = InlineRuntime(fn=_failing_callable)
        result = rt.run(_run_json())
        assert result.exit_code == 1
        assert not result.ok
        assert b"ValueError: boom" in result.stderr

    def test_system_exit_returns_exit_code(self):
        rt = InlineRuntime(fn=_exit_callable)
        result = rt.run(_run_json())
        assert result.exit_code == 42
        assert not result.ok

    def test_receives_run_json(self):
        rt = InlineRuntime(fn=_reads_model_spec)
        result = rt.run(_run_json())
        assert result.ok
        assert result.stdout.strip() == b"test"

    def test_creates_filesystem_output_dir(self, tmp_path):
        out_dir = tmp_path / "nested" / "output"
        transport = _run_json(output={"spec": "filesystem", "dir": str(out_dir)})
        rt = InlineRuntime(fn=_noop_callable)
        result = rt.run(transport)
        assert result.ok
        assert out_dir.exists()

    def test_restores_stdout_stderr_on_exception(self):
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        rt = InlineRuntime(fn=_failing_callable)
        rt.run(_run_json())
        assert sys.stdout is original_stdout
        assert sys.stderr is original_stderr


# --- resolve_runtime ---


class TestResolveRuntime:
    def test_process_runtime(self):
        config = {
            "runtime": {
                "spec": "process",
                "command": "python3",
                "args": ["-c", "pass"],
            }
        }
        rt = resolve_runtime(config)
        assert isinstance(rt, SubprocessRuntime)
        assert rt.command == ["python3", "-c", "pass"]

    def test_process_runtime_missing_command(self):
        config = {"runtime": {"spec": "process"}}
        with pytest.raises(ValueError, match="command is required"):
            resolve_runtime(config)

    def test_inline_runtime(self):
        config = {
            "runtime": {
                "spec": "inline",
                "callable": "json:loads",
            }
        }
        rt = resolve_runtime(config)
        assert isinstance(rt, InlineRuntime)
        assert rt.fn is json.loads

    def test_inline_runtime_missing_callable(self):
        config = {"runtime": {"spec": "inline"}}
        with pytest.raises(ValueError, match="callable is required"):
            resolve_runtime(config)

    def test_unknown_spec(self):
        config = {"runtime": {"spec": "wasm"}}
        with pytest.raises(ValueError, match="Unknown runtime spec"):
            resolve_runtime(config)

    def test_invalid_callable_path(self):
        config = {
            "runtime": {
                "spec": "inline",
                "callable": "no_colon_here",
            }
        }
        with pytest.raises(ValueError, match="module:attr"):
            resolve_runtime(config)

    def test_process_runtime_with_profile(self):
        config = {
            "runtime": {
                "profile": {
                    "local": {
                        "spec": "process",
                        "command": "python3",
                        "args": ["-c", "pass"],
                    },
                    "remote": {
                        "spec": "process",
                        "command": "docker",
                        "args": ["run", "model"],
                    },
                }
            }
        }
        rt = resolve_runtime(config, runtime_profile="local")
        assert isinstance(rt, SubprocessRuntime)
        assert rt.command == ["python3", "-c", "pass"]

    def test_process_runtime_profile_default(self):
        config = {
            "runtime": {
                "profile": {
                    "default": {
                        "spec": "process",
                        "command": "python3",
                        "args": ["-c", "pass"],
                    },
                }
            }
        }
        rt = resolve_runtime(config)
        assert isinstance(rt, SubprocessRuntime)
        assert rt.command == ["python3", "-c", "pass"]
