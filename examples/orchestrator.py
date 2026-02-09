#!/usr/bin/env python3
"""Example: merging experiment files with a base config using mrp.run().

The base config (mrp.toml) defines model, runtime, and output settings.
Experiment files in experiments/ contain only input overrides. We load
each experiment TOML and pass it as overrides to mrp.run(), which
deep-merges them into the base config.
"""

from pathlib import Path

from mrp import run
from mrp.config import load_toml

BASE_CONFIG = Path("examples/renewal/mrp.toml")
EXPERIMENTS_DIR = Path("examples/renewal/experiments")

# Run each experiment file against the base config
for experiment_file in sorted(EXPERIMENTS_DIR.glob("*.toml")):
    experiment = load_toml(experiment_file)

    result = run(
        BASE_CONFIG,
        overrides=experiment,
        output_dir=f"./output/{experiment_file.stem}/",
    )

    r0 = experiment.get("input", {}).get("r0", "base")
    print(f"{experiment_file.name} (r0={r0}) — ok: {result.ok}")
