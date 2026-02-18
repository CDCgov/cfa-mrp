
# MRP for Model Authors

## What is mrp?

`mrp` (Model Run Protocol) is a protocol and set of tools that makes
your model ready to run in a number of runtimes (such as via the
command line, in Docker, WASM, etc.) and with any mrp-compatible
**plugin** or tool (such as the cfa-calibration package).

It has a standard format for reading **inputs** (parameters and files)
and **producing outputs** (like CSV files).

## Integration guide

### Install `cfa-mrp`

```bash
uv add cfa-mrp
```

### Add an MRP environment to your model

The MRP environment parses input sources for you, and gives you an API to write files.

In this example, we construct an environment directly:

```python
from mrp import Environment


def run():
    env = Environment().load()
    values = env.rng.random(10).tolist()
    env.write_csv(
        "output.csv",
        {"step": list(range(len(values))), "value": values},
    )
```

Or you can implement the `MRPModel` class, which accepts all the
same arguments as `.load()`:

```python
from mrp import MRPModel


class Model(MRPModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.parameters = Parameters(**self.input)


    def run(self):
        n = self.parameters.n
        values = self.rng.random(n).tolist()
        self.write_csv(
            "output.csv",
            {"step": list(range(len(values))), "value": values},


# Uses args=True by default
Model().run()

# With config files and overrides
Model(configs=["defaults.toml"], json={"input": {"seed": 1}}).run()
```

Your model needs to be runnable as a command. See
[Sample architectures](#sample-architectures) below for how to set
this up.

### Create a config file

Create a file called `mrp.toml` in your project:

```toml
[model]
spec = "my-model"
version = "0.1.0"

[runtime]
command = "uv run renewal"

[output]
spec = "filesystem"
dir = "./output"

[input]
seed = 0
r0 = 2.0
population_size = 100000
sim_length = 200
```

You can also point `input` at a JSON file instead of inlining
values:

```toml
input = "parameters.json"
```

| Section     | Purpose                                          |
|-------------|--------------------------------------------------|
| `[model]`   | Name and version of your model                   |
| `[runtime]` | How to run your model (command + args)            |
| `[output]`  | Where to write results                            |
| `[input]`   | Default parameters passed to your model           |

### Run your model, with optional arguments

```bash
mrp run mrp.toml --input seed=42
```

## Overriding parameters

### From the CLI

Use `--input` to override input parameters. It accepts key=value
pairs, JSON files, or inline JSON:

```bash
# Key=value pair
mrp run config.toml --input r0=4.0

# Multiple values
mrp run config.toml --input r0=4.0 --input seed=42

# From a JSON file
mrp run config.toml --input params.json

# Inline JSON
mrp run config.toml --input '{"r0": 4.0, "seed": 42}'

# Override the output directory
mrp run config.toml --output-dir ./my_output/
```

### From code with `.load()`

`Environment().load()` merges configuration in this order
(later wins):

1. CLI arguments — `--input` and `--set` (if `args=True`)
2. Config files in order (JSON or TOML)
3. `json` dict

```python
from mrp import Environment

# Just CLI --set args
env = Environment().load(args=True)

# CLI args + config files + programmatic overrides
env = Environment().load(
    args=True,
    configs=["defaults.toml", "large.toml"],
    json={"input": {"seed": 99}},
    resolve="merge",
)
```

`--input seed=42` sets `{"input": {"seed": 42}}` directly.
`--set input.seed=42` does the same using dotted paths. Values
are automatically parsed as numbers/booleans when possible,
falling back to strings.

## Sample architectures

### Python package (Function)

A minimal Python model as a runnable module:

```text
mymodel.mrp.toml
mymodel/
  __init__.py
  __main__.py
  model.py

```

**`model.py`:**

```python
from mrp import Environment


def run():
    env = Environment().load(args=True)
    values = env.rng.random(10).tolist()
    env.write_csv(
        "output.csv",
        {"step": list(range(len(values))), "value": values},
    )
```

**`__main__.py`:**

```python
from .model import run

if __name__ == "__main__":
    run()
```

**`mymodel.mrp.toml`:**

```toml
[model]
spec = "mymodel"
version = "0.1.0"

[runtime]
env = "uv"
command = "mymodel"

[output]
spec = "filesystem"
dir = "./results/"

[input]
r0 = 2.0
sim_length = 200
```

### Python package (Class)

For more complex models, extend `MRPModel` which provides
`self.input`, `self.rng`, `self.files`, and output methods:

**`model.py`:**

```python
from mrp import MRPModel


class Model(MRPModel):
    def run(self):
        r0 = float(self.input.get("r0", 2.0))
        values = self.rng.random(10).tolist()
        self.write_csv(
            "output.csv",
            {"step": list(range(len(values))), "value": values},
        )
```

**`__main__.py`:**

```python
from .model import Model

if __name__ == "__main__":
    Model(configs=["defaults.toml"]).run()
```

## Using staged files

If your model needs external data files, declare them in the config
under `model.files`. MRP will download remote files and stage them
locally before running your model.

```toml
[model]
spec = "my-model"
version = "0.1.0"
files = { data = "https://example.com/data.csv" }
```

Access them in your model via `env.files`:

```python
env = Environment().load(args=True)
data_path = env.files["data"]  # Path to the staged local file
```

## Full examples

See the complete renewal model examples in
[examples/renewal](../examples/renewal) (Python) and
[examples/renewal-rs](../examples/renewal-rs) (Rust).
