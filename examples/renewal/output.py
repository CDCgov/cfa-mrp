from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass
class RenewalOutput:
    infection_incidence: NDArray[np.uint64]
    symptomatic_incidence: NDArray[np.uint64]

    @staticmethod
    def new(length: int) -> "RenewalOutput":
        return RenewalOutput(
            infection_incidence=np.zeros(length, dtype=np.uint64),
            symptomatic_incidence=np.zeros(length, dtype=np.uint64),
        )
