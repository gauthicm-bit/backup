"""Synthetic-history generator interface (contract §2.3)."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar, Literal

import numpy as np

GeneratorType = Literal["garch", "timegan", "diffusion"]


class Generator(ABC):
    type: ClassVar[GeneratorType]

    @abstractmethod
    def fit(self, returns: np.ndarray) -> "Generator": ...

    @abstractmethod
    def sample(self, n_paths: int, length: int, seed: int) -> np.ndarray: ...

    @abstractmethod
    def save(self, path: Path) -> None: ...

    @classmethod
    @abstractmethod
    def load(cls, path: Path) -> "Generator": ...
