from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Parameters:
    r0: float
    generation_interval_pmf: list[float]
    symptom_onset_pmf: list[float]
    initial_infections: list[int]
    sim_length: int
    population_size: int | None = None
