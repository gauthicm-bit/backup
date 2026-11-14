"""GJR-GARCH(1,1) fitted by arch with standardized Student-t innovations."""

import json
from pathlib import Path
from typing import ClassVar

import numpy as np
from arch import arch_model

from engine.common import GeneratorNotTrained
from engine.generators.base import Generator, GeneratorType


class GarchGenerator(Generator):
    type: ClassVar[GeneratorType] = "garch"

    def __init__(self) -> None:
        self.state: dict[str, float] | None = None

    def fit(self, returns: np.ndarray) -> "GarchGenerator":
        values = np.asarray(returns, dtype=np.float64)
        if (
            values.ndim != 1
            or values.size < 100
            or not np.isfinite(values).all()
            or values.std() <= 0
        ):
            raise ValueError("GARCH requires at least 100 finite, nonconstant log returns")
        # Percentage scaling makes numerical optimisation stable for daily returns.
        fitted = arch_model(
            values * 100,
            mean="Constant",
            vol="GARCH",
            p=1,
            o=1,
            q=1,
            dist="StudentsT",
            rescale=False,
        ).fit(disp="off", show_warning=False)
        if fitted.convergence_flag:
            raise ValueError("GARCH fit did not converge")
        params = fitted.params
        self.state = {
            "mu": float(params["mu"]),
            "omega": float(params["omega"]),
            "alpha": float(params["alpha[1]"]),
            "gamma": float(params["gamma[1]"]),
            "beta": float(params["beta[1]"]),
            "nu": float(params["nu"]),
            "variance": float(fitted.conditional_volatility[-1] ** 2),
            "residual": float(fitted.resid[-1]),
        }
        return self

    def sample(self, n_paths: int, length: int, seed: int) -> np.ndarray:
        if self.state is None:
            raise GeneratorNotTrained("Fit GARCH on this audit's real returns before sampling")
        if n_paths <= 0 or length <= 0 or seed < 0:
            raise ValueError("n_paths and length must be positive and seed nonnegative")
        state = self.state
        rng = np.random.default_rng(seed)
        variance = np.full(n_paths, state["variance"], dtype=np.float64)
        residual = np.full(n_paths, state["residual"], dtype=np.float64)
        paths = np.empty((n_paths, length), dtype=np.float64)
        scale = np.sqrt((state["nu"] - 2) / state["nu"])
        # All paths start from the fitted history's final conditional state.
        # Draw one time slice at a time to avoid a second (n_paths,T) allocation.
        for t in range(length):
            variance = (
                state["omega"]
                + state["alpha"] * residual**2
                + state["gamma"] * residual**2 * (residual < 0)
                + state["beta"] * variance
            )
            variance = np.maximum(variance, np.finfo(np.float64).tiny)
            residual = np.sqrt(variance) * rng.standard_t(state["nu"], n_paths) * scale
            paths[:, t] = (state["mu"] + residual) / 100
        if not np.isfinite(paths).all():
            raise ValueError("GARCH simulation produced nonfinite returns")
        return paths

    def save(self, path: Path) -> None:
        if self.state is None:
            raise GeneratorNotTrained("Cannot save an unfitted GARCH generator")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.state, sort_keys=True, allow_nan=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "GarchGenerator":
        generator = cls()
        generator.state = json.loads(Path(path).read_text(encoding="utf-8"))
        return generator
