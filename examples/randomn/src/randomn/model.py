from dataclasses import dataclass

from mrp import MRPModel


@dataclass
class Parameters:
    n: int = 10


class Model(MRPModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.parameters: Parameters = Parameters(**self.input)

    def run(self):
        n = self.parameters.n
        values = self.rng.random(n).tolist()
        self.write_csv(
            "output.csv",
            {"step": list(range(len(values))), "value": values},
        )


def main():
    Model().run()