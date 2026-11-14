"""Contract §2.5 realism shapes and deterministic statistic bands."""

import numpy as np

from engine.realism.stylized_facts import run_realism


def test_identical_paths_put_real_inside_all_bands():
    real = np.random.default_rng(42).standard_t(6, 800) * 0.01
    result = run_realism(real, np.tile(real, (10, 1)))
    assert len(result.tests) == 8
    assert all(t.passed for t in result.tests)
    assert result.density_x.shape == (200,)
    assert result.acf_lags.tolist() == list(range(1, 51))
    np.testing.assert_allclose(result.real_density, result.syn_density_p50)


def test_constant_returns_stay_finite():
    result = run_realism(np.zeros(300), np.zeros((2, 300)))
    assert all(np.isfinite(t.real) for t in result.tests)
    assert np.isfinite(result.acf_sq_real).all()
