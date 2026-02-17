from mrp import MRPModel

from .parameters import Parameters


class Model(MRPModel):
    """A stochastic renewal model for infectious disease transmission.

    Simulates disease spread using the renewal equation, where new
    infections at each time step depend on recent infections weighted
    by a generation interval distribution. Supports both finite
    (binomial) and infinite (poisson) population modes.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.parameters = Parameters(**self.input)

    def simulate(self) -> tuple[dict[str, list], dict[str, list]]:
        """Run the simulation and return infection and symptom onset time series.

        Returns:
            A tuple of two dicts, each with "step" and "count" keys:
            (infections, symptom_onsets).
        """
        p = self.parameters
        n = p.sim_length
        infections = [0] * n
        symptom_onsets = [0] * n
        rt = [p.r0] * n
        cum_infected = 0

        for step in range(n):
            inf = self._compute_infections(step, infections, rt, cum_infected)
            infections[step] = inf
            cum_infected += inf

            # Update rt for finite populations
            if p.population_size is not None and step < n - 1:
                rt[step + 1] = (
                    p.r0 * (p.population_size - cum_infected) / p.population_size
                )

            self._distribute_symptom_onsets(step, inf, symptom_onsets)

        steps = list(range(n))
        return (
            {"step": steps, "count": infections},
            {"step": steps, "count": symptom_onsets},
        )

    def _compute_infections(
        self,
        step: int,
        infections: list[int],
        rt: list[float],
        cum_infected: int,
    ) -> int:
        """Compute new infections at a given time step"""
        p = self.parameters

        if step < len(p.initial_infections):
            return p.initial_infections[step]

        # Renewal equation
        current_infectious = sum(
            infections[step - lag - 1] * p.generation_interval_pmf[lag]
            for lag in range(min(step, len(p.generation_interval_pmf)))
        )
        transmission_rate = rt[step] * current_infectious

        if p.population_size is not None:
            susceptible = p.population_size - cum_infected
            if susceptible <= 0:
                return 0
            prob = min(transmission_rate / susceptible, 1.0)
            return int(self.rng.binomial(susceptible, prob))

        if transmission_rate > 0.0:
            return int(self.rng.poisson(transmission_rate))
        return 0

    def _distribute_symptom_onsets(
        self, step: int, inf: int, symptom_onsets: list[int]
    ) -> None:
        """Distribute symptom onsets from infections at a given step"""
        if inf <= 0:
            return

        n = self.parameters.sim_length
        residual_mass = 1.0
        cum_onsets = 0
        for i, mass in enumerate(self.parameters.symptom_onset_pmf):
            onset_step = step + 1 + i
            if onset_step >= n:
                break
            prob = mass / residual_mass
            onsets = int(self.rng.binomial(inf - cum_onsets, prob))
            symptom_onsets[onset_step] += onsets
            cum_onsets += onsets
            residual_mass -= mass

    def run(self):
        infections, symptom_onsets = self.simulate()
        self.write_csv("infections.csv", infections)
        self.write_csv("symptom_onsets.csv", symptom_onsets)


def main():
    Model().run()
