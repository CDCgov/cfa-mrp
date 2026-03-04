from dataclasses import dataclass

from numpy.random import SeedSequence, default_rng

from mrp import MRPModel


@dataclass
class Parameters:
    n: int
    seed: int = 0


class Model(MRPModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.parameters: Parameters = Parameters(**self.input)

    def run(self):
        n = self.parameters.n
        rng = default_rng(SeedSequence(self.parameters.seed))
        values = rng.random(n).tolist()
        self.write_csv(
            "output.csv",
            {"step": list(range(len(values))), "value": values},
        )


def main():
    Model().run()
