from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass
class Parameters:
    r0: float
    generation_interval_pmf: NDArray[np.float64]
    symptom_onset_pmf: NDArray[np.float64]
    initial_infections: NDArray[np.uint64]
    sim_length: int
    population_size: int | None = None
