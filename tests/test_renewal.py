from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from numpy.random import SeedSequence, default_rng

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "examples" / "renewal" / "src")
)

from renewal.model import Model
from renewal.parameters import Parameters


class TestFinalSize:
    def test_final_size(self):
        population = 100_000
        parameters = Parameters(
            population_size=population,
            r0=2.0,
            generation_interval_pmf=np.array([0.0, 0.0, 0.25, 0.5, 0.25]),
            symptom_onset_pmf=np.array([1.0]),
            initial_infections=np.array([1], dtype=np.uint64),
            sim_length=200,
        )
        rng = default_rng(SeedSequence(8675308))
        infections, _ = Model(parameters, rng).simulate()
        cum_infected = sum(infections["count"])
        fraction_infected = cum_infected / population
        # Final size for r0=2.0 is ~0.796811
        assert abs(fraction_infected - 0.796811) < 0.1


class TestGenerationInterval:
    def test_generation_interval(self):
        n_samples = 10000
        initial_infections = 100
        gi_pmf = np.array([0.0, 0.0, 0.25, 0.5, 0.25])

        cumulative_output = np.zeros(len(gi_pmf) + 1, dtype=np.uint64)
        total = 0

        for seed in range(n_samples):
            parameters = Parameters(
                r0=1.0,
                generation_interval_pmf=gi_pmf.copy(),
                symptom_onset_pmf=np.array([1.0]),
                initial_infections=np.array([initial_infections], dtype=np.uint64),
                sim_length=len(gi_pmf) + 1,
            )
            rng = default_rng(SeedSequence(seed))
            infections, _ = Model(parameters, rng).simulate()
            for i in range(len(cumulative_output)):
                incidence = infections["count"][i]
                cumulative_output[i] += incidence
                if i > 0:
                    total += incidence

        for step, mass in enumerate(gi_pmf):
            fraction = int(cumulative_output[step + 1]) / total
            assert abs(fraction - mass) < 1e-3
