from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "examples" / "renewal" / "src")
)

from mrp.environment import Environment
from renewal.model import Model
from renewal.parameters import Parameters

_BASE_INPUT = {
    "r0": 2.0,
    "population_size": 100_000,
    "generation_interval_pmf": [0.0, 0.0, 0.25, 0.5, 0.25],
    "symptom_onset_pmf": [1.0],
    "initial_infections": [1],
    "sim_length": 200,
}


def _make_model(input_overrides: dict | None = None, seed: int = 0) -> Model:
    inp = {**_BASE_INPUT, **(input_overrides or {})}
    env = Environment({"input": {**inp, "seed": seed}})
    return Model(env=env, args=False)


class TestFinalSize:
    def test_final_size(self):
        population = 100_000
        model = _make_model(
            {"population_size": population, "r0": 2.0},
            seed=8675308,
        )
        infections, _ = model.simulate()
        cum_infected = sum(infections["count"])
        fraction_infected = cum_infected / population
        # Final size for r0=2.0 is ~0.796811
        assert abs(fraction_infected - 0.796811) < 0.1


class TestGenerationInterval:
    def test_generation_interval(self):
        n_samples = 10000
        initial_infections = 100
        gi_pmf = [0.0, 0.0, 0.25, 0.5, 0.25]

        cumulative_output = np.zeros(len(gi_pmf) + 1, dtype=np.uint64)
        total = 0

        for seed in range(n_samples):
            model = _make_model(
                {
                    "r0": 1.0,
                    "population_size": None,
                    "generation_interval_pmf": gi_pmf[:],
                    "initial_infections": [initial_infections],
                    "sim_length": len(gi_pmf) + 1,
                },
                seed=seed,
            )
            infections, _ = model.simulate()
            for i in range(len(cumulative_output)):
                incidence = infections["count"][i]
                cumulative_output[i] += incidence
                if i > 0:
                    total += incidence

        for step, mass in enumerate(gi_pmf):
            fraction = int(cumulative_output[step + 1]) / total
            assert abs(fraction - mass) < 1e-3
