"""Environment — model-side SDK for the MRP JSON transport."""

from __future__ import annotations

import copy
import csv
import json
import sys
import tomllib
from pathlib import Path

from numpy.random import Generator, SeedSequence, default_rng


def _read_file(path: Path) -> dict:
    if path.suffix == ".toml":
        with open(path, "rb") as f:
            return tomllib.load(f)
    with open(path) as f:
        return json.load(f)


def _read_stdin() -> dict:
    if sys.stdin.isatty():
        return {}
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    return json.loads(raw)


def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _parse_cli_sets() -> dict:
    """Parse --set key=value pairs from sys.argv into a nested dict.

    Dotted keys create nested structure: --set input.seed=42
    produces {"input": {"seed": 42}}.
    """
    result: dict = {}
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        if argv[i] == "--set" and i + 1 < len(argv):
            pair = argv[i + 1]
            i += 2
        elif argv[i].startswith("--set="):
            pair = argv[i][len("--set=") :]
            i += 1
        else:
            i += 1
            continue

        key, _, raw_value = pair.partition("=")
        if not key or not _:
            continue

        # Try to parse as JSON for typed values (numbers, bools, etc.)
        try:
            value = json.loads(raw_value)
        except (json.JSONDecodeError, ValueError):
            value = raw_value

        # Build nested dict from dotted key
        parts = key.split(".")
        target = result
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = value

    return result


class Environment:
    def __init__(self, data: dict | None = None):
        data = data or {}
        self.input = dict(data.get("input", {}))
        self.seed = int(self.input.pop("seed", 0))
        self.replicate = int(self.input.pop("replicate", 0))
        model = data.get("model", {})
        self.files = {k: Path(v) for k, v in model.get("files", {}).items()}
        self._output = data.get("output", {})
        self._rng: Generator | None = None
        self._csv_writers: dict[str, CsvWriter] = {}

    @property
    def rng(self) -> Generator:
        """Numpy random Generator seeded via SeedSequence."""
        if self._rng is None:
            self._rng = default_rng(SeedSequence(self.seed))
        return self._rng

    def load(
        self,
        *,
        args: bool = False,
        stdin: bool = True,
        configs: list[str] | None = None,
        json: dict | None = None,
        resolve: str = "merge",
    ) -> Environment:
        """Load environment from multiple sources.

        Merge order (later wins):
        1. stdin (JSON, if stdin=True and data is available)
        2. --set key=value CLI arguments (if args=True)
        3. Config files in order (JSON/TOML)
        4. json dict

        Args:
            args: Parse --set key=value pairs from sys.argv.
            stdin: Read JSON from stdin (default True).
            configs: List of file paths (JSON or TOML).
            json: Dict of overrides.
            resolve: Merge strategy. Currently only "merge" (deep merge).
        """
        result: dict = {}
        if stdin:
            result = _deep_merge(result, _read_stdin())
        if args:
            result = _deep_merge(result, _parse_cli_sets())
        for path in configs or []:
            result = _deep_merge(result, _read_file(Path(path)))
        if json is not None:
            result = _deep_merge(result, json)
        self.__init__(result)
        return self

    @classmethod
    def from_args(cls, *sources: dict | str) -> Environment:
        """Create from one or more sources, merged left to right.

        Each source can be:
        - "stdin" — read JSON from stdin
        - a file path (str) — JSON or TOML based on extension
        - a dict — used directly

        Later sources override earlier ones on conflicts.
        """
        if not sources:
            sources = ("stdin",)
        result: dict = {}
        for source in sources:
            if isinstance(source, dict):
                resolved = source
            elif source == "stdin":
                resolved = _read_stdin()
            else:
                resolved = _read_file(Path(source))
            result = _deep_merge(result, resolved)
        return cls(result)

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

    def create_csv(self, id: str, filename: str, fieldnames: list[str]) -> None:
        self._csv_writers[id] = self.csv_writer(filename, fieldnames)

    def write_csv_row(self, id: str, row: list | dict) -> None:
        self._csv_writers[id].write_row(row)

    def close_csv(self, id: str) -> None:
        self._csv_writers.pop(id).close()

    def close_all_csv(self) -> None:
        for w in self._csv_writers.values():
            w.close()
        self._csv_writers.clear()

    def csv_writer(self, filename: str, fieldnames: list[str]) -> CsvWriter:
        if self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            f = open(self.output_dir / filename, "w", newline="")
        else:
            f = sys.stdout
        return CsvWriter(f, fieldnames, close=f is not sys.stdout)

    def write_csv(self, filename: str, columns: dict[str, list]):
        fieldnames = list(columns.keys())
        values = list(columns.values())
        n_rows = len(values[0]) if values else 0
        rows = [{k: columns[k][i] for k in fieldnames} for i in range(n_rows)]
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


class CsvWriter:
    def __init__(self, f, fieldnames: list[str], *, close: bool = True):
        self._f = f
        self._close = close
        self._writer = csv.writer(f)
        self._fieldnames = fieldnames
        self._writer.writerow(fieldnames)

    def write_row(self, row: list | dict):
        if isinstance(row, dict):
            self._writer.writerow([row[k] for k in self._fieldnames])
        else:
            self._writer.writerow(row)

    def close(self):
        if self._close:
            self._f.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
