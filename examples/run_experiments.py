import argparse
from pathlib import Path
from typing import Any

from mrp import Orchestrator
from mrp.api import apply_dict_overrides
from mrp.config import load_toml
from mrp.runtime import RunResult, Runtime


class ExperimentOrchestrator(Orchestrator):
    def __init__(self, experiments=None, replicates=1):
        self.experiments = experiments
        self.replicates = replicates

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--experiments",
            type=Path,
            required=True,
            help="Directory of experiment TOML files",
        )
        parser.add_argument(
            "--replicates",
            type=int,
            default=1,
            help="Number of replicates per experiment",
        )

    def execute(self, config: dict[str, Any], runtime: Runtime) -> RunResult:
        last = RunResult(exit_code=0, stdout=b"", stderr=b"")

        for exp_file in sorted(self.experiments.glob("*.toml")):
            experiment = load_toml(exp_file)
            experiment_name = exp_file.stem

            for replicate in range(self.replicates):
                merged = apply_dict_overrides(config, experiment)
                merged = apply_dict_overrides(merged, {"input": {"seed": replicate}})

                run_json = self.build_run(
                    merged,
                    output_dir=f"./output/{experiment_name}/{replicate}/",
                )
                last = self.run(run_json, runtime)
                print(f"{experiment_name} rep={replicate} — ok: {last.ok}")

        return last


if __name__ == "__main__":
    from mrp.cli import main

    main(orchestrator=ExperimentOrchestrator())
