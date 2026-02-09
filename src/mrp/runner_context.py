"""RunnerContext — model-side SDK for the MRP JSON transport."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from numpy.random import Generator, SeedSequence, default_rng


class RunnerContext:
    def __init__(self, data: dict):
        self.input = dict(data.get("input", {}))
        self.seed = int(self.input.pop("seed", 0))
        self.replicate = int(self.input.pop("replicate", 0))
        model = data.get("model", {})
        self.files = {k: Path(v) for k, v in model.get("files", {}).items()}
        self._output = data.get("output", {})
        self._rng: Generator | None = None

    @property
    def rng(self) -> Generator:
        """Numpy random Generator seeded via SeedSequence."""
        if self._rng is None:
            self._rng = default_rng(SeedSequence(self.seed))
        return self._rng

    @classmethod
    def from_stdin(cls):
        raw = sys.stdin.read()
        if not raw.strip():
            print("Error: no input on stdin", file=sys.stderr)
            sys.exit(1)
        return cls(json.loads(raw))

    @classmethod
    def from_run_json(cls, run_json: dict) -> RunnerContext:
        """Construct from a run JSON transport dict."""
        return cls(run_json)

    @property
    def output_dir(self) -> Path | None:
        output = self._output
        # Check flat output
        if output.get("spec") == "filesystem":
            d = output.get("dir")
            if d:
                return Path(d)
            return None
        # Check profiled output — resolve default profile
        profiles = output.get("profile")
        if profiles:
            selected = profiles.get("default") or next(iter(profiles.values()), None)
            if selected and selected.get("spec") == "filesystem":
                d = selected.get("dir")
                if d:
                    return Path(d)
        return None

    def write(self, filename: str, data: str | bytes):
        if self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            mode = "wb" if isinstance(data, bytes) else "w"
            with open(self.output_dir / filename, mode) as f:
                f.write(data)
        else:
            if isinstance(data, bytes):
                sys.stdout.buffer.write(data)
            else:
                sys.stdout.write(data)

    def write_csv(self, filename: str, rows: list[dict], fieldnames: list[str]):
        if self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            with open(self.output_dir / filename, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
                w.writerows(rows)
        else:
            w = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
