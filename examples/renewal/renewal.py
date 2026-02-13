#!/usr/bin/env python3
"""Renewal model using the MRP Environment SDK."""

from __future__ import annotations

import numpy as np
from numpy.random import Generator

from .output import RenewalOutput
from .parameters import Parameters


class RenewalModel:
    @staticmethod
    def simulate(parameters: Parameters, rng: Generator) -> RenewalOutput:
        output = RenewalOutput.new(parameters.sim_length)
        rt = np.full(parameters.sim_length, parameters.r0)
        cum_infected: int = 0

        gi_pmf = parameters.generation_interval_pmf
        so_pmf = parameters.symptom_onset_pmf

        for step in range(parameters.sim_length):
            if step < len(parameters.initial_infections):
                infections = int(parameters.initial_infections[step])
            else:
                # Renewal equation
                current_infectious = 0.0
                for lag in range(min(step, len(gi_pmf))):
                    current_infectious += (
                        output.infection_incidence[step - lag - 1] * gi_pmf[lag]
                    )
                transmission_rate = rt[step] * current_infectious

                if parameters.population_size is not None:
                    susceptible = parameters.population_size - cum_infected
                    if susceptible > 0:
                        p = min(transmission_rate / susceptible, 1.0)
                        infections = int(rng.binomial(susceptible, p))
                    else:
                        infections = 0
                else:
                    if transmission_rate > 0.0:
                        infections = int(rng.poisson(transmission_rate))
                    else:
                        infections = 0

            output.infection_incidence[step] = infections
            cum_infected += infections

            # Update rt for finite populations
            if (
                parameters.population_size is not None
                and step < parameters.sim_length - 1
            ):
                rt[step + 1] = (
                    parameters.r0
                    * (parameters.population_size - cum_infected)
                    / parameters.population_size
                )

            # Distribute symptom onset times
            if infections > 0:
                residual_mass = 1.0
                cum_onsets = 0
                for i, mass in enumerate(so_pmf):
                    onset_step = step + 1 + i
                    if onset_step >= parameters.sim_length:
                        break
                    p = mass / residual_mass
                    onsets = int(rng.binomial(infections - cum_onsets, p))
                    output.symptomatic_incidence[onset_step] += onsets
                    cum_onsets += onsets
                    residual_mass -= mass

        return output


def main():
    from mrp import Environment

    ctx = Environment.from_stdin()
    inp = ctx.input

    pop_size = inp.get("population_size")

    parameters = Parameters(
        population_size=int(pop_size) if pop_size else None,
        r0=float(inp.get("r0", 2.0)),
        generation_interval_pmf=np.array(
            inp["generation_interval_pmf"], dtype=np.float64
        ),
        symptom_onset_pmf=np.array(
            inp.get("symptom_onset_pmf", [1.0]), dtype=np.float64
        ),
        initial_infections=np.array(
            inp.get("initial_infections", [1]), dtype=np.uint64
        ),
        sim_length=int(inp.get("sim_length", 200)),
    )

    output = RenewalModel.simulate(parameters, ctx.rng)

    rows = [
        {
            "step": i,
            "infections": int(output.infection_incidence[i]),
            "symptom_onsets": int(output.symptomatic_incidence[i]),
        }
        for i in range(parameters.sim_length)
    ]
    ctx.write_csv(
        "renewal_output.csv",
        rows,
        fieldnames=["step", "infections", "symptom_onsets"],
    )


if __name__ == "__main__":
    main()
