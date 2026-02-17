"""MRPModel — base class for model authors."""

from __future__ import annotations

import abc
from pathlib import Path

from numpy.random import Generator

from mrp.environment import Environment


class MRPModel(abc.ABC):
    def __init__(
        self,
        env: Environment | None = None,
        *,
        args: bool = True,
        configs: list[str] | None = None,
        json: dict | None = None,
        resolve: str = "merge",
    ):
        self.env = env or Environment().load(
            args=args, configs=configs, json=json, resolve=resolve,
        )

    @property
    def input(self) -> dict:
        return self.env.input

    @property
    def rng(self) -> Generator:
        return self.env.rng

    @property
    def files(self) -> dict[str, Path]:
        return self.env.files

    def write(self, filename: str, data: str | bytes):
        self.env.write(filename, data)

    def write_csv(self, filename: str, columns: dict[str, list]):
        self.env.write_csv(filename, columns)

    @abc.abstractmethod
    def run(self) -> None: ...
