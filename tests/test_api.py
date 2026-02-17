"""Tests for mrp.run() programmatic API."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pytest

import mrp
from mrp.api import apply_dict_overrides, run
from mrp.orchestrator import Orchestrator
from mrp.runtime import RunResult, Runtime

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class TestApplyDictOverrides:
    def test_shallow_override(self):
        config = {"input": {"r0": 2.0}}
        result = apply_dict_overrides(config, {"input": {"r0": 3.0}})
        assert result["input"]["r0"] == 3.0
        assert config["input"]["r0"] == 2.0  # original not mutated

    def test_deep_merge_preserves_siblings(self):
        config = {"input": {"r0": 2.0, "sim_length": 200}}
        result = apply_dict_overrides(config, {"input": {"r0": 3.0}})
        assert result["input"]["r0"] == 3.0
        assert result["input"]["sim_length"] == 200

    def test_adds_new_keys(self):
        config = {"input": {}}
        result = apply_dict_overrides(config, {"input": {"new_key": 42}})
        assert result["input"]["new_key"] == 42

    def test_adds_new_sections(self):
        config = {"input": {"r0": 2.0}}
        result = apply_dict_overrides(config, {"extra": {"key": "val"}})
        assert result["extra"]["key"] == "val"
        assert result["input"]["r0"] == 2.0

    def test_empty_overrides(self):
        config = {"input": {"r0": 2.0}}
        result = apply_dict_overrides(config, {})
        assert result == config


def _echo_model_script(expr: str) -> list[str]:
    """Return args for a subprocess that reads stdin JSON and prints *expr*."""
    return ["-c", f"import sys,json; d=json.load(sys.stdin); print({expr})"]


class TestRunWithDict:
    def test_subprocess_ok(self):
        config = {
            "model": {"spec": "test"},
            "runtime": {
                "spec": "process",
                "command": sys.executable,
                "args": _echo_model_script("'ok'"),
            },
            "input": {},
            "output": {"spec": "stdout"},
        }
        result = run(config)
        assert isinstance(result, RunResult)
        assert result.ok
        assert b"ok" in result.stdout

    def test_overrides_applied(self):
        config = {
            "model": {"spec": "test"},
            "runtime": {
                "spec": "process",
                "command": sys.executable,
                "args": _echo_model_script("d['input']['x']"),
            },
            "input": {"x": 1},
            "output": {"spec": "stdout"},
        }
        result = run(config, {"input": {"x": 99}})
        assert result.ok
        assert b"99" in result.stdout

    def test_config_dict_not_mutated(self):
        config = {
            "model": {"spec": "test"},
            "runtime": {
                "spec": "process",
                "command": sys.executable,
                "args": ["-c", "import sys; sys.stdin.read()"],
            },
            "input": {"x": 1},
            "output": {"spec": "stdout"},
        }
        run(config, {"input": {"x": 99}})
        assert config["input"]["x"] == 1


class TestRunWithPath:
    def test_toml_file(self):
        result = run(FIXTURES / "mrp.with_profiles.toml")
        assert isinstance(result, RunResult)
        assert result.ok

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            run("/nonexistent/path.toml")

    def test_invalid_config_type(self):
        with pytest.raises(TypeError):
            run(42)  # type: ignore[arg-type]


class _StubRuntime(Runtime):
    """Minimal custom runtime for testing."""

    def __init__(self):
        self.last_run_json = None

    def run(self, run_json):
        self.last_run_json = run_json
        return RunResult(exit_code=0, stdout=b"stub-ok", stderr=b"")


class _StubOrchestrator(Orchestrator):
    """Orchestrator that builds run_json and executes via stub runtime."""

    def __init__(self):
        self.last_config = None

    def execute(self, config, runtime):
        self.last_config = config
        run_json = self.build_run(config)
        stub = _StubRuntime()
        result = self.run(run_json, stub)
        self.last_run_json = stub.last_run_json
        return result


class TestRunWithOrchestrator:
    def test_custom_orchestrator_used(self):
        config = {
            "model": {"spec": "test"},
            "input": {},
            "output": {"spec": "stdout"},
        }
        orch = _StubOrchestrator()
        result = run(config, orchestrator=orch)
        assert result.ok
        assert result.stdout == b"stub-ok"
        assert orch.last_run_json is not None
        assert orch.last_run_json["model"]["spec"] == "test"

    def test_orchestrator_receives_original_config(self):
        """Config passed to orchestrator retains command/args."""
        config = {
            "model": {"spec": "test"},
            "runtime": {
                "spec": "process",
                "command": "python3",
                "args": ["-m", "my_model"],
            },
            "input": {"x": 1},
            "output": {"spec": "stdout"},
        }
        orch = _StubOrchestrator()
        run(config, orchestrator=orch)
        # run_json should have command/args stripped
        assert "command" not in orch.last_run_json.get("runtime", {})
        # config should retain command/args
        assert orch.last_config["runtime"]["command"] == "python3"
        assert orch.last_config["runtime"]["args"] == ["-m", "my_model"]

    def test_orchestrator_receives_all_profiles(self):
        """When no profile is selected, orchestrator sees all profiles."""
        config = {
            "model": {"spec": "test"},
            "runtime": {
                "profile": {
                    "local": {
                        "spec": "process",
                        "command": "python3",
                        "args": ["-m", "my_model"],
                    },
                    "docker": {
                        "spec": "docker",
                        "command": "python3",
                        "args": ["-m", "my_model"],
                    },
                }
            },
            "input": {},
            "output": {"spec": "stdout"},
        }
        orch = _StubOrchestrator()
        run(config, orchestrator=orch)
        profiles = orch.last_config["runtime"]["profile"]
        assert "local" in profiles
        assert "docker" in profiles

    def test_orchestrator_receives_overrides(self):
        config = {
            "model": {"spec": "test"},
            "input": {"x": 1},
            "output": {"spec": "stdout"},
        }
        orch = _StubOrchestrator()
        run(config, {"input": {"x": 99}}, orchestrator=orch)
        assert orch.last_run_json["input"]["x"] == 99

    def test_no_runtime_section_with_orchestrator(self):
        """Config with no [runtime] section works when orchestrator is provided."""
        config = {
            "model": {"spec": "test"},
            "input": {},
            "output": {"spec": "stdout"},
        }
        result = run(config, orchestrator=_StubOrchestrator())
        assert result.ok


class TestLoadConfig:
    def test_load_single_dict(self):
        orch = _StubOrchestrator()
        config = orch.load_config({"input": {"x": 1}})
        assert config["input"]["x"] == 1

    def test_merge_multiple_dicts(self):
        orch = _StubOrchestrator()
        config = orch.load_config(
            {"input": {"x": 1, "y": 2}},
            {"input": {"x": 99}},
        )
        assert config["input"]["x"] == 99
        assert config["input"]["y"] == 2

    def test_load_toml_file(self):
        orch = _StubOrchestrator()
        config = orch.load_config(FIXTURES / "mrp.toml")
        assert "model" in config

    def test_file_not_found(self):
        orch = _StubOrchestrator()
        with pytest.raises(FileNotFoundError):
            orch.load_config("/nonexistent/path.toml")

    def test_invalid_type(self):
        orch = _StubOrchestrator()
        with pytest.raises(TypeError):
            orch.load_config(42)  # type: ignore[arg-type]

    def test_no_configs(self):
        orch = _StubOrchestrator()
        with pytest.raises(ValueError, match="At least one config"):
            orch.load_config()

    def test_overrides_applied(self):
        orch = _StubOrchestrator()
        config = orch.load_config(
            {"input": {"x": 1}},
            overrides=["input.x=99"],
        )
        assert config["input"]["x"] == 99

    def test_dict_not_mutated(self):
        orch = _StubOrchestrator()
        original = {"input": {"x": 1}}
        orch.load_config(original, {"input": {"x": 99}})
        assert original["input"]["x"] == 1


class TestResolveRuntime:
    def test_no_runtime_returns_none(self):
        orch = _StubOrchestrator()
        assert orch.resolve_runtime({"input": {}}) is None

    def test_empty_runtime_returns_none(self):
        orch = _StubOrchestrator()
        assert orch.resolve_runtime({"runtime": {}}) is None

    def test_process_runtime(self):
        from mrp.runtime.subprocess import SubprocessRuntime

        orch = _StubOrchestrator()
        runtime = orch.resolve_runtime({
            "runtime": {
                "spec": "process",
                "command": "echo",
                "args": ["hello"],
            }
        })
        assert isinstance(runtime, SubprocessRuntime)


class TestOrchestratorHooks:
    def test_add_arguments_called(self):
        """add_arguments is invoked on the orchestrator by the CLI."""

        class _ArgOrch(Orchestrator):
            def __init__(self):
                self.parser_seen = None

            def add_arguments(self, parser):
                self.parser_seen = parser
                parser.add_argument("--foo", default="bar")

            def execute(self, config, runtime):
                return RunResult(exit_code=0, stdout=b"", stderr=b"")

        orch = _ArgOrch()
        parser = argparse.ArgumentParser()
        orch.add_arguments(parser)
        assert orch.parser_seen is parser
        ns = parser.parse_args(["--foo", "baz"])
        assert ns.foo == "baz"


class TestTopLevelExports:
    def test_run_exported(self):
        assert hasattr(mrp, "run")
        assert callable(mrp.run)

    def test_run_result_exported(self):
        assert mrp.RunResult is RunResult

    def test_runtime_exported(self):
        assert mrp.Runtime is Runtime

    def test_orchestrator_exported(self):
        assert mrp.Orchestrator is Orchestrator

    def test_resolve_runtime_exported(self):
        from mrp.runtime import resolve_runtime

        assert mrp.resolve_runtime is resolve_runtime
