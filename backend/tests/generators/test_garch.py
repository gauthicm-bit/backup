"""Seed reproducibility and persistence (API contract §2.3)."""

import numpy as np
import pytest

from engine.common import GeneratorNotTrained
from engine.generators import get_generator, is_available
from engine.generators.garch import GarchGenerator


@pytest.fixture
def fitted():
    returns = np.random.default_rng(42).standard_t(7, 1000) * 0.01
    return GarchGenerator().fit(returns)


def test_garch_is_available_and_challengers_unavailable():
    assert is_available("garch")
    assert isinstance(get_generator("garch"), GarchGenerator)
    for name in ["timegan", "diffusion", "unknown"]:
        assert not is_available(name)
        with pytest.raises(GeneratorNotTrained):
            get_generator(name)


def test_deterministic_shape_and_no_nan(fitted):
    first = fitted.sample(10, 300, 42)
    assert first.shape == (10, 300)
    assert first.dtype == np.float64
    assert np.isfinite(first).all()
    np.testing.assert_array_equal(first, fitted.sample(10, 300, 42))
    assert not np.array_equal(first, fitted.sample(10, 300, 43))


def test_save_load_reproduces_samples(fitted, tmp_path):
    path = tmp_path / "garch.json"
    fitted.save(path)
    restored = GarchGenerator.load(path)
    np.testing.assert_array_equal(fitted.sample(10, 50, 23), restored.sample(10, 50, 23))


def test_sample_requires_fit():
    with pytest.raises(GeneratorNotTrained):
        GarchGenerator().sample(2, 30, 42)


@pytest.mark.parametrize("returns", [np.array([]), np.zeros(200), np.full(200, np.nan)])
def test_bad_training_data_rejected(returns):
    with pytest.raises(ValueError):
        GarchGenerator().fit(returns)
