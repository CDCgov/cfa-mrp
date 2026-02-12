from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
import pytest

from mrp import RunnerContext


def _transport(*, input=None, files=None, output=None):
    """Build a minimal MRP transport dict."""
    data = {}
    if input is not None:
        data["input"] = input
    if files is not None:
        data.setdefault("model", {})["files"] = files
    if output is not None:
        data["output"] = output
    return data


# --- Constructor ---


class TestInit:
    def test_extracts_input(self):
        ctx = RunnerContext(_transport(input={"r0": 2.5, "gamma": 0.1}))
        assert ctx.input == {"r0": 2.5, "gamma": 0.1}

    def test_pops_seed_and_replicate(self):
        ctx = RunnerContext(_transport(input={"r0": 2.5, "seed": 42, "replicate": 3}))
        assert ctx.seed == 42
        assert ctx.replicate == 3
        assert "seed" not in ctx.input
        assert "replicate" not in ctx.input
        assert ctx.input == {"r0": 2.5}

    def test_defaults_seed_and_replicate_to_zero(self):
        ctx = RunnerContext(_transport(input={"r0": 2.5}))
        assert ctx.seed == 0
        assert ctx.replicate == 0

    def test_coerces_seed_and_replicate_to_int(self):
        ctx = RunnerContext(_transport(input={"seed": "7", "replicate": "2"}))
        assert ctx.seed == 7
        assert ctx.replicate == 2

    def test_empty_data(self):
        ctx = RunnerContext({})
        assert ctx.input == {}
        assert ctx.seed == 0
        assert ctx.replicate == 0
        assert ctx.files == {}
        assert ctx.output_dir is None

    def test_files_as_paths(self):
        ctx = RunnerContext(
            _transport(
                files={"population": "/data/pop.csv", "geo": "relative/geo.json"}
            )
        )
        assert ctx.files["population"] == Path("/data/pop.csv")
        assert ctx.files["geo"] == Path("relative/geo.json")
        assert isinstance(ctx.files["population"], Path)

    def test_input_is_a_copy(self):
        original = {"r0": 2.5}
        ctx = RunnerContext(_transport(input=original))
        ctx.input["r0"] = 999
        assert original["r0"] == 2.5


# --- rng ---


class TestRng:
    def test_returns_numpy_generator(self):
        ctx = RunnerContext(_transport(input={"seed": 42}))
        assert isinstance(ctx.rng, np.random.Generator)

    def test_deterministic(self):
        ctx1 = RunnerContext(_transport(input={"seed": 42}))
        ctx2 = RunnerContext(_transport(input={"seed": 42}))
        assert ctx1.rng.random() == ctx2.rng.random()

    def test_different_seeds_differ(self):
        ctx1 = RunnerContext(_transport(input={"seed": 1}))
        ctx2 = RunnerContext(_transport(input={"seed": 2}))
        assert ctx1.rng.random() != ctx2.rng.random()

    def test_cached(self):
        ctx = RunnerContext(_transport(input={"seed": 42}))
        assert ctx.rng is ctx.rng


# --- output_dir ---


class TestOutputDir:
    def test_filesystem_sink(self):
        ctx = RunnerContext(
            _transport(output={"spec": "filesystem", "dir": "./results/run_0000/"})
        )
        assert ctx.output_dir == Path("./results/run_0000/")

    def test_no_output(self):
        ctx = RunnerContext(_transport())
        assert ctx.output_dir is None

    def test_non_filesystem_output_ignored(self):
        ctx = RunnerContext(
            _transport(output={"spec": "az", "container": "my-container"})
        )
        assert ctx.output_dir is None

    def test_profiled_output_default(self):
        ctx = RunnerContext(
            _transport(
                output={
                    "profile": {
                        "default": {
                            "spec": "filesystem",
                            "dir": "./output/run_0000/",
                        },
                        "stdout": {"spec": "stdout"},
                    }
                }
            )
        )
        assert ctx.output_dir == Path("./output/run_0000/")

    def test_profiled_output_first_key(self):
        ctx = RunnerContext(
            _transport(
                output={
                    "profile": {
                        "local": {
                            "spec": "filesystem",
                            "dir": "./local/run_0000/",
                        },
                    }
                }
            )
        )
        assert ctx.output_dir == Path("./local/run_0000/")


# --- from_stdin ---


class TestFromStdin:
    def test_parses_json_from_stdin(self, monkeypatch):
        data = _transport(input={"r0": 3.0, "seed": 10})
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(data)))
        ctx = RunnerContext.from_stdin()
        assert ctx.input == {"r0": 3.0}
        assert ctx.seed == 10

    def test_exits_on_empty_stdin(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO(""))
        with pytest.raises(SystemExit, match="1"):
            RunnerContext.from_stdin()

    def test_exits_on_whitespace_stdin(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", io.StringIO("   \n  "))
        with pytest.raises(SystemExit, match="1"):
            RunnerContext.from_stdin()


# --- from_run_json ---


class TestFromRunJson:
    def test_constructs_from_run_json(self):
        data = _transport(input={"r0": 3.0, "seed": 10})
        ctx = RunnerContext.from_run_json(data)
        assert ctx.input == {"r0": 3.0}
        assert ctx.seed == 10


# --- write ---


class TestWrite:
    def test_writes_string_to_filesystem(self, tmp_path):
        ctx = RunnerContext(
            _transport(output={"spec": "filesystem", "dir": str(tmp_path / "out")})
        )
        ctx.write("hello.txt", "hello world")
        assert (tmp_path / "out" / "hello.txt").read_text() == "hello world"

    def test_writes_bytes_to_filesystem(self, tmp_path):
        ctx = RunnerContext(
            _transport(output={"spec": "filesystem", "dir": str(tmp_path / "out")})
        )
        ctx.write("data.bin", b"\x00\x01\x02")
        assert (tmp_path / "out" / "data.bin").read_bytes() == b"\x00\x01\x02"

    def test_creates_nested_dirs(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c"
        ctx = RunnerContext(_transport(output={"spec": "filesystem", "dir": str(deep)}))
        ctx.write("f.txt", "ok")
        assert (deep / "f.txt").read_text() == "ok"

    def test_string_to_stdout_when_no_sink(self, monkeypatch):
        buf = io.StringIO()
        monkeypatch.setattr("sys.stdout", buf)
        ctx = RunnerContext(_transport())
        ctx.write("ignored.txt", "stdout content")
        assert buf.getvalue() == "stdout content"

    def test_bytes_to_stdout_when_no_sink(self, monkeypatch):
        buf = io.BytesIO()
        monkeypatch.setattr("sys.stdout", type("FakeStdout", (), {"buffer": buf})())
        ctx = RunnerContext(_transport())
        ctx.write("ignored.bin", b"\xff\xfe")
        assert buf.getvalue() == b"\xff\xfe"


# --- write_csv ---


class TestWriteCsv:
    ROWS = [
        {"step": 0, "day": 0.0, "S": 9990.0},
        {"step": 1, "day": 1.0, "S": 9985.0},
    ]
    FIELDS = ["step", "day", "S"]

    def test_writes_csv_to_filesystem(self, tmp_path):
        ctx = RunnerContext(
            _transport(output={"spec": "filesystem", "dir": str(tmp_path / "out")})
        )
        ctx.write_csv("data.csv", self.ROWS, self.FIELDS)
        content = (tmp_path / "out" / "data.csv").read_text()
        lines = content.strip().split("\n")
        assert lines[0] == "step,day,S"
        assert lines[1] == "0,0.0,9990.0"
        assert lines[2] == "1,1.0,9985.0"

    def test_writes_csv_to_stdout_when_no_sink(self, monkeypatch):
        buf = io.StringIO()
        monkeypatch.setattr("sys.stdout", buf)
        ctx = RunnerContext(_transport())
        ctx.write_csv("ignored.csv", self.ROWS, self.FIELDS)
        lines = buf.getvalue().strip().splitlines()
        assert lines[0] == "step,day,S"
        assert len(lines) == 3

    def test_empty_rows(self, tmp_path):
        ctx = RunnerContext(
            _transport(output={"spec": "filesystem", "dir": str(tmp_path)})
        )
        ctx.write_csv("empty.csv", [], ["a", "b"])
        content = (tmp_path / "empty.csv").read_text()
        assert content.strip() == "a,b"
