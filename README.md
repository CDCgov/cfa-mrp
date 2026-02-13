# CFA Model Run Protocol (CFA-MRP)

## Overview

MRP is a layered protocol for running computational
disease models. It defines a standard interface between
tooling and model code: **a model is a function that
accepts JSON and produces output.**

The SDK handles config parsing, file staging, and runtime
dispatch — so models stay simple.

## General Disclaimer

**General disclaimer** This repository was created for use by CDC programs to
collaborate on public health related projects in support of the
[CDC mission](https://www.cdc.gov/about/cdc/#cdc_about_cio_mission-our-mission).
GitHub is not hosted by the CDC, but is a third party website used by CDC and
its partners to share information and collaborate on software. CDC use of GitHub
does not imply an endorsement of any one particular service, product, or
enterprise.

See also the longer [Disclaimer](DISCLAIMER.md) and the [Notices](#Notices)
section below.

## Quick start

Requires Python 3.11+,
[uv](https://docs.astral.sh/uv/), and
[poethepoet](https://poethepoet.naez.io/)
for task running. You can install `poe` globally with `uv install poethepoet`,
or alternatively call `poe [task]`.

### Run a model

The repo includes an example renewal model:

```bash
poe renewal
```

Or run directly with custom options:

```bash
uv run mrp run examples/renewal/mrp.toml
```

This produces output in `results/`.

### Override parameters from the CLI

```bash
# Change a model parameter
uv run mrp run examples/renewal/mrp.toml --set input.r0=4.0

# Select profiles for profiled configs
uv run mrp run examples/renewal/mrp.with_profiles.toml \
  --profile runtime=local
```

### Run an orchestrator

The included example runs multiple experiments against
a base config, merging input overrides from each
experiment file:

```bash
uv run python examples/orchestrator.py
```

You can also write a custom orchestrator by subclassing
`mrp.Orchestrator` and passing it to `mrp.run()`:

```python
import mrp
from mrp.orchestrator import Orchestrator
from mrp.runtime import RunResult, resolve_runtime

class MyOrchestrator(Orchestrator):
    def run(self, run_json, config):
        runtime = resolve_runtime(config)
        return runtime.run(run_json)

result = mrp.run("config.toml", orchestrator=MyOrchestrator())
```

See `examples/orchestrator.py` for a full working example.

## How it works

MRP operates across three protocol layers:

```text
L2  Translation       TOML -> JSON, file staging
L1  Runtime Adapter   subprocess, WASM, in-process
L0  Model             accepts JSON, produces output
```

The key idea: **models only see L0.** A model reads a JSON
document from stdin and writes output. It has no knowledge
of config files or file staging.

The TOML config mirrors the JSON transport format
directly — see `examples/renewal/mrp.toml` for a simple
config and `examples/renewal/mrp.with_profiles.toml` for
a profiled config with named runtime/output variants.

See [spec/protocol.md](spec/protocol.md) for the full
protocol specification, including the JSON transport
format, TOML config mapping, runtime adapters, output
sinks, and CLI options.

## Writing a model

A model is any executable that reads JSON from stdin and
writes output. The `Environment` class handles all the
protocol boilerplate so model code can focus on
computation:

```python
from mrp import Environment

ctx = Environment.from_stdin()

# Access input params
r0 = ctx.input["r0"]
seed = ctx.seed        # reads input["seed"] if present
replicate = ctx.replicate  # reads input["replicate"]

# Use the seeded numpy Generator directly
rng = ctx.rng
noise = rng.normal(0, 0.01)

# Access staged files
pop_path = ctx.files["population"]  # returns Path

# Write CSV output (routed to filesystem or stdout)
ctx.write_csv(
    "output.csv", rows,
    fieldnames=["step", "infections", "symptom_onsets"],
)

# Or write raw string/bytes
ctx.write("output.bin", some_bytes)
```

`Environment.from_stdin()` reads and parses the JSON
transport from stdin. For testing, construct directly:
`Environment({"input": {"r0": 2.5}})`.

Output routing is automatic — if a filesystem sink is
configured in the transport, `write` and `write_csv`
write to that directory; otherwise they write to stdout.

The included example (`examples/renewal/renewal.py`)
demonstrates the full pattern.

## Python API

Use `mrp.run()` to run models programmatically:

```python
import mrp

# Run from a TOML config file
result = mrp.run("examples/renewal/mrp.toml")
print(result.ok)  # True

# Override parameters
result = mrp.run(
    "examples/renewal/mrp.toml",
    overrides={"input": {"r0": 3.0, "sim_length": 50}},
    output_dir="./my_output/",
)

# Run from a dict config
result = mrp.run({
    "model": {
        "spec": "renewal-model",
        "version": "0.1.0",
    },
    "runtime": {
        "spec": "process",
        "command": "python3",
        "args": ["-m", "examples.renewal.renewal"],
    },
    "input": {
        "r0": 2.0,
        "population_size": 100000,
    },
    "output": {
        "spec": "filesystem",
        "dir": "./results/",
    },
})

# Select profiles
result = mrp.run(
    "examples/renewal/mrp.with_profiles.toml",
    runtime_profile="local",
    output_profile="stdout",
)
```

`mrp.run()` returns a `RunResult`:

| Field | Type | Description |
|---|---|---|
| `exit_code` | `int` | Process exit code |
| `stdout` | `bytes` | Captured stdout |
| `stderr` | `bytes` | Captured stderr |
| `ok` | `bool` | `True` if `exit_code == 0` |

See `examples/orchestrator.py` for a working example
of merging experiment files with a base config.

## Project layout

```text
spec/protocol.md              — Full protocol spec
src/mrp/environment.py        — Environment (model SDK)
src/mrp/cli.py                — CLI entry point (mrp run)
src/mrp/api.py                — Programmatic API (mrp.run)
src/mrp/config.py             — TOML parsing, translation
src/mrp/runtime/__init__.py   — Re-exports, resolve_runtime
src/mrp/runtime/base.py       — Runtime ABC, RunResult
src/mrp/runtime/subprocess.py — Subprocess adapter
src/mrp/runtime/inline.py     — Inline adapter
src/mrp/stager.py             — File staging (URI -> path)
examples/renewal/             — Example renewal model
examples/renewal/experiments/ — Experiment input overrides
examples/orchestrator.py      — Multi-experiment runner
tests/                        — Unit and fixture tests
```

See `spec/protocol.md` for the full specification.

## Developing the MRP library

### Tasks

Common workflows are defined as
[poe](https://poethepoet.naez.io/) tasks
in `pyproject.toml`:

| Task | Command | Description |
|---|---|---|
| `poe test` | `pytest` | Run tests |
| `poe lint` | `ruff check .` | Lint Python |
| `poe typecheck` | `ty check src` | Type check |
| `poe renewal` | `mrp run ...` | Run renewal example |

## Notices

### Public Domain Standard Notice

This repository constitutes a work of the United States Government and is not
subject to domestic copyright protection under 17 USC § 105. This repository is in
the public domain within the United States, and copyright and related rights in
the work worldwide are waived through the [CC0 1.0 Universal public domain dedication](https://creativecommons.org/publicdomain/zero/1.0/).
All contributions to this repository will be released under the CC0 dedication. By
submitting a pull request you are agreeing to comply with this waiver of
copyright interest.

### License Standard Notice

The repository utilizes code licensed under the terms of the Apache Software
License and therefore is licensed under ASL v2 or later.

This source code in this repository is free: you can redistribute it and/or modify it under
the terms of the Apache Software License version 2, or (at your option) any
later version.

This source code in this repository is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the Apache Software License for more details.

You should have received a copy of the Apache Software License along with this
program. If not, see <http://www.apache.org/licenses/LICENSE-2.0.html>

The source code forked from other open source projects will inherit its license.

### Privacy Standard Notice

This repository contains only non-sensitive, publicly available data and
information. All material and community participation is covered by the
[Disclaimer](DISCLAIMER.md)
and [Code of Conduct](code-of-conduct.md).
For more information about CDC's privacy policy, please visit [http://www.cdc.gov/other/privacy.html](https://www.cdc.gov/other/privacy.html).

### Contributing Standard Notice

Anyone is encouraged to contribute to the repository by [forking](https://help.github.com/articles/fork-a-repo)
and submitting a pull request. (If you are new to GitHub, you might start with a
[basic tutorial](https://help.github.com/articles/set-up-git).) By contributing
to this project, you grant a world-wide, royalty-free, perpetual, irrevocable,
non-exclusive, transferable license to all users under the terms of the
[Apache Software License v2](http://www.apache.org/licenses/LICENSE-2.0.html) or
later.

All comments, messages, pull requests, and other submissions received through
CDC including this GitHub page may be subject to applicable federal law, including but not limited to the Federal Records Act, and may be archived. Learn more at [http://www.cdc.gov/other/privacy.html](http://www.cdc.gov/other/privacy.html).

### Records Management Standard Notice

This repository is not a source of government records, but is a copy to increase
collaboration and collaborative potential. All government records will be
published through the [CDC web site](http://www.cdc.gov).
